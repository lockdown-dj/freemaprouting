# Fuel Route API

A Django REST API that, given a start and finish location in the US, returns
a driving route, the cheapest sequence of fuel stops along that route (given
a 500-mile vehicle range), and the total projected fuel cost at 10 MPG.

## Contents

- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [API](#api)
- [External API usage](#external-api-usage-vs-the-one-call-ideal-requirement)
- [Performance](#performance)
- [Assumptions & known limitations](#assumptions--known-limitations)
- [Tests](#tests)
- [Project layout](#project-layout)

## Quick start

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # defaults are fine for local dev

python manage.py migrate

# Load fuel prices. This geocodes every unique (city, state) pair in the
# CSV via Nominatim (rate-limited to 1 req/sec by its usage policy), so
# a full load of ~3,900 unique pairs takes roughly an hour THE FIRST TIME.
# Progress is cached to data/geocode_cache.json and safe to Ctrl-C/resume.
python manage.py load_fuel_stations

# For a fast local smoke test instead of the full geocoded load:
python manage.py load_fuel_stations --skip-geocoding --limit 500

python manage.py runserver
```

Then:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "Los Angeles, CA", "finish": "New York, NY"}'
```

## How it works

**Request flow** (`routing/views.py`):

1. Geocode `start` and `finish` (Nominatim) -> lat/lon. Cached.
2. Call OSRM **once** for the full driving route (geometry + distance +
   duration). Cached.
3. Turn the route geometry into a cumulative-distance-indexed polyline
   (`RoutePolyline`, in `routing/services/fuel_optimizer.py`).
4. **Corridor match**: find which fuel stations (from the DB, already
   geocoded at load time) actually lie along the route. A cheap DB
   bounding-box query prefilters candidates, then a vectorized (numpy)
   point-to-polyline distance check keeps only stations within
   `ROUTE_CORRIDOR_MILES` (default 12mi) of the driving path, and records
   each one's approximate mile-marker position along the route.
5. **Optimize**: a greedy algorithm (`plan_fuel_stops`) walks the route
   deciding where to stop and how much fuel to buy, to minimize total
   spend without ever exceeding the vehicle's range between fill-ups.
6. Build a viewable static map URL (no extra API call — see below) and
   return everything as JSON.

**The fuel-stop algorithm.** This is the classic "bounded tank, variable
price, continuous purchase" cost-minimization problem. At any point where a
purchase decision can be made (the start, or a station just arrived at), the
vehicle can see every station reachable on a full tank from there:

- If a **cheaper** station is reachable, buy only enough fuel *now* to reach
  it (minimizing gallons bought at the pricier stop), then repeat the
  decision there.
- If **nothing cheaper** is reachable, this is the best price available
  before running out of range — so fill the tank **completely**, then drive
  to the cheapest reachable station.
- If the **destination itself** is reachable on a full tank and nothing
  cheaper lies on the way, skip further stops entirely and buy just enough
  to finish the trip.

This greedy is provably optimal under the continuous-purchase assumption
(you can buy any fractional number of gallons) — see `routing/tests/
test_fuel_optimizer.py` for worked-through cases.

## API

### `POST /api/v1/route/`

**Request body**

| Field         | Type   | Required | Default             | Notes                                  |
|---------------|--------|----------|----------------------|-----------------------------------------|
| `start`       | string | yes      | —                    | e.g. `"Los Angeles, CA"`, or a full address |
| `finish`      | string | yes      | —                    | e.g. `"New York, NY"`               |
| `range_miles` | number | no       | 500 (`VEHICLE_RANGE_MILES`) | vehicle's max range per full tank |
| `mpg`         | number | no       | 10 (`VEHICLE_MPG`)          | vehicle's fuel economy            |

**Response (200)**

```jsonc
{
  "start": {"query": "Los Angeles, CA", "display_name": "...", "latitude": 34.05, "longitude": -118.24},
  "finish": {"query": "New York, NY", "display_name": "...", "latitude": 40.71, "longitude": -74.0},
  "distance_miles": 2775.4,
  "duration_hours": 41.3,
  "vehicle": {"range_miles": 500, "mpg": 10},
  "route_geometry": [[34.05, -118.24], ["..."], [40.71, -74.0]],
  "map_image_url": "https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=...",
  "fuel_stops": [
    {
      "name": "PILOT TRAVEL CENTER #1243", "city": "Gila Bend", "state": "AZ",
      "address": "I-8, EXIT 119 & SR-85", "latitude": 32.94, "longitude": -112.7,
      "price_per_gallon": 3.899, "position_along_route_miles": 481.2,
      "distance_from_route_miles": 3.1, "gallons_purchased": 44.7, "cost": 174.28
    }
  ],
  "total_fuel_stops": 6,
  "total_gallons_purchased": 232.7,
  "total_fuel_cost_usd": 812.55,
  "assumptions": ["..."]
}
```

**Error responses**: `400` invalid input, `422` a location couldn't be
geocoded / no feasible fuel plan exists for the route, `502` the routing
service failed.

## External API usage vs. the "one call ideal" requirement

Per request: **one** OSRM routing call (cached thereafter for that
start/finish pair) plus up to **two** Nominatim geocoding calls (one per
location, each cached independently — a repeated location, e.g. re-planning
from the same city, costs zero further geocode calls). Everything else
(corridor matching, the optimizer, map URL construction) runs in-process
against data already in the database — no further external calls.

The one-time bulk geocoding of the fuel-price CSV (`load_fuel_stations`) is
deliberately kept **out of the request path entirely** — it's an offline
data-load step, not something the API does per-request.

## Performance

The corridor-matching and optimizer steps are pure in-process computation
(numpy-vectorized distance calculations, no I/O). Benchmarked locally
against a synthetic ~2,500-mile coast-to-coast route with 4,000 candidate
stations: **~0.5 seconds** end-to-end for matching + optimization (see
commit history / Loom for a live run). The only latency outside Claude's
control is the two geocode calls and one OSRM call on a cache miss;
identical repeat requests are served straight from cache.

## Assumptions & known limitations

- **Starting tank**: the vehicle starts at `start` with a full tank, so no
  fuel purchase is required until the first fill-up becomes necessary.
- **Station coordinates are city-level**, not exact-address-level. The
  source CSV's `Address` column is a highway/exit description (e.g. `"I-44,
  EXIT 283 & US-69"`), not a geocodable street address, so stations are
  geocoded by `(city, state)` instead. This is precise enough to match
  stations to a ~12-mile-wide driving corridor but not to a specific exit;
  a production version would enrich the dataset with real station
  coordinates (e.g. a paid station-locator API) instead.
- **Prices are static**, taken as-is from the CSV (no date/inflation
  adjustment).
- **OSRM's public demo server** is free but rate-limited and not intended
  for production traffic — fine for this exercise; a production deployment
  should self-host OSRM (open source) or use a commercial routing provider.
- If a stretch of the route exceeds `range_miles` with no station within
  reach anywhere along it, the API returns a `422` explaining the gap,
  rather than silently returning an incomplete/unsafe plan.

## Tests

```bash
python manage.py test routing
```

Covers: the greedy optimizer's decision logic (cheaper-station detours,
full-tank fill-ups, exact final-leg top-offs, infeasible-route detection),
corridor matching against a real (test) database, and the full view
end-to-end with geocoding/routing mocked (no network needed to run tests).

## Project layout

```
fuel_route_api/          # Django project settings/urls
routing/
  models.py              # FuelStation
  views.py                # RoutePlanView (the one API endpoint)
  serializers.py          # request/response schemas
  exceptions.py            # domain errors -> clean JSON error responses
  services/
    geocoding.py           # Nominatim client (+ disk cache for bulk loads)
    routing_client.py      # OSRM client (one call per route)
    fuel_optimizer.py      # corridor matching + the greedy fuel-stop algorithm
  management/commands/
    load_fuel_stations.py  # offline CSV load + one-time geocoding
  tests/
data/
  fuel_prices.csv          # the supplied dataset
```
