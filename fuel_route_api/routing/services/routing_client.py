"""
Thin client for OSRM (Open Source Routing Machine), used via the free,
keyless public demo server at router.project-osrm.org.

Exactly ONE call is made to this API per route-planning request (the
requirement's ideal case): a single `/route/v1/driving/{lon,lat;lon,lat}`
request with `overview=full` returns the full route geometry plus total
distance/duration in one shot -- no need for separate calls per leg.

Note: the public demo server is rate-limited and explicitly not intended
for heavy production traffic (see OSRM's usage policy). For production
use, self-host OSRM (it's open source) or swap in a commercial provider
behind this same interface.
"""

import logging

import requests
from django.conf import settings

from routing.exceptions import RoutingError

logger = logging.getLogger(__name__)

METERS_PER_MILE = 1609.344


def get_route(start_lat, start_lon, end_lat, end_lon) -> dict:
    """
    Returns:
        {
            "distance_miles": float,
            "duration_seconds": float,
            "geometry": [[lat, lon], ...],   # ordered list along the route
        }
    """
    coords = f"{start_lon},{start_lat};{end_lon},{end_lat}"
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{coords}"

    try:
        response = requests.get(
            url,
            params={"overview": "full", "geometries": "geojson", "steps": "false"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("OSRM routing request failed: %s", exc)
        raise RoutingError("Routing service error while computing the driving route.") from exc

    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RoutingError(
            "No driving route could be found between the supplied locations. "
            f"({payload.get('message', payload.get('code', 'unknown error'))})"
        )

    route = payload["routes"][0]
    coordinates_lon_lat = route["geometry"]["coordinates"]
    geometry_lat_lon = [[lat, lon] for lon, lat in coordinates_lon_lat]

    return {
        "distance_miles": route["distance"] / METERS_PER_MILE,
        "duration_seconds": route["duration"],
        "geometry": geometry_lat_lon,
    }
