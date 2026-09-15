const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  PageOrientation, VerticalAlign, TabStopType, TabStopPosition,
} = require("docx");

// ---------- palette / type ----------
const INK = "161B22";
const INK_SOFT = "525C6B";
const INK_FAINT = "8891A0";
const ROUTE = "0B3FE0";
const ROUTE_SOFT = "E7ECFC";
const FUEL = "C2410C";
const FUEL_SOFT = "FBEAE0";
const CODE_BG = "111826";
const CODE_FG = "DCE4ED";
const CODE_COMMENT = "8695A8";
const LINE = "D8DDE5";

const F_HEAD = "Calibri";
const F_BODY = "Calibri";
const F_MONO = "Consolas";

const PAGE_W = 12240, PAGE_H = 15840, MARGIN = 1260;
const CONTENT_W = PAGE_W - MARGIN * 2;

// ---------- helpers ----------
function hr() {
  return new Paragraph({
    spacing: { before: 160, after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LINE } },
  });
}

function eyebrow(text, color = ROUTE) {
  return new Paragraph({
    spacing: { after: 90 },
    children: [
      new TextRun({
        text, bold: true, color, font: F_HEAD, size: 16,
        allCaps: true, characterSpacing: 20,
      }),
    ],
  });
}

function codeBlock(lines) {
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color: "232B38" },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: "232B38" },
      left: { style: BorderStyle.SINGLE, size: 2, color: "232B38" },
      right: { style: BorderStyle.SINGLE, size: 2, color: "232B38" },
    },
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: CONTENT_W, type: WidthType.DXA },
            shading: { type: ShadingType.CLEAR, fill: CODE_BG },
            margins: { top: 160, bottom: 160, left: 220, right: 220 },
            children: lines.map((line) => {
              const text = typeof line === "string" ? line : line.text;
              const comment = typeof line === "object" && line.comment;
              return new Paragraph({
                spacing: { after: 24 },
                children: [
                  new TextRun({
                    text: text.length ? text : " ",
                    font: F_MONO, size: 18,
                    color: comment ? CODE_COMMENT : CODE_FG,
                    italics: !!comment,
                  }),
                ],
              });
            }),
          }),
        ],
      }),
    ],
  });
}

function calloutBox(paras, fill = FUEL_SOFT, textColor = INK_SOFT) {
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color: LINE },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: LINE },
      left: { style: BorderStyle.SINGLE, size: 2, color: LINE },
      right: { style: BorderStyle.SINGLE, size: 2, color: LINE },
    },
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: CONTENT_W, type: WidthType.DXA },
            shading: { type: ShadingType.CLEAR, fill },
            margins: { top: 160, bottom: 160, left: 220, right: 220 },
            children: paras.map(
              (p) =>
                new Paragraph({
                  spacing: { after: 80 },
                  children: [
                    ...(p.label
                      ? [new TextRun({ text: p.label + " ", bold: true, color: INK, font: F_BODY, size: 20 })]
                      : []),
                    new TextRun({ text: p.text, color: textColor, font: F_BODY, size: 20 }),
                  ],
                })
            ),
          }),
        ],
      }),
    ],
  });
}

function narrationParas(paras) {
  return paras.map(
    (p) =>
      new Paragraph({
        spacing: { after: 120 },
        indent: { left: 130 },
        border: { left: { style: BorderStyle.SINGLE, size: 18, color: ROUTE_SOFT, space: 8 } },
        children: [
          ...(p.beat
            ? [
                new TextRun({
                  text: p.beat + "  ",
                  bold: true, font: F_MONO, size: 15, color: INK_FAINT,
                }),
              ]
            : []),
          new TextRun({ text: p.text, font: F_BODY, size: 21, color: INK }),
        ],
      })
  );
}

function actionNote(text) {
  return new Paragraph({
    spacing: { before: 60, after: 0 },
    indent: { left: 130 },
    children: [
      new TextRun({ text: "ACTION  ", bold: true, italics: false, font: F_MONO, size: 14, color: FUEL }),
      new TextRun({ text, italics: true, font: F_BODY, size: 19, color: INK_SOFT }),
    ],
  });
}

function sceneHeading(num, title, timecode, fileLabel) {
  return [
    new Paragraph({
      spacing: { before: 380, after: 20 },
      tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
      children: [
        new TextRun({ text: `${num}`, bold: true, font: F_HEAD, size: 22, color: "FFFFFF" }),
      ],
      shading: { type: ShadingType.CLEAR, fill: num === "0" || num === "13" ? ROUTE : INK_FAINT },
    }),
    new Paragraph({
      heading: HeadingLevel.HEADING_2,
      spacing: { before: 40, after: 20 },
      tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
      children: [
        new TextRun({ text: `Scene ${num} — ${title}`, bold: true, font: F_HEAD, size: 27, color: INK }),
        new TextRun({ text: `\t${timecode}`, bold: false, font: F_MONO, size: 18, color: FUEL }),
      ],
    }),
    new Paragraph({
      spacing: { after: 130 },
      children: [new TextRun({ text: fileLabel, italics: true, font: F_MONO, size: 17, color: ROUTE })],
    }),
  ];
}

function colLabel(text) {
  return new Paragraph({
    spacing: { before: 140, after: 70 },
    children: [
      new TextRun({ text, bold: true, font: F_HEAD, size: 15, color: INK_FAINT, allCaps: true, characterSpacing: 20 }),
    ],
  });
}

// ---------- rundown table ----------
const rundown = [
  ["0:00", "Cold open"], ["0:25", "Premise"], ["0:50", "Project skeleton"],
  ["1:35", "The data model"], ["2:20", "The contract at the door"], ["3:05", "The orchestrator"],
  ["4:30", "Names → coordinates"], ["5:20", "One call to the road"], ["5:50", "Corridor matching"],
  ["7:10", "The greedy algorithm"], ["9:15", "Clean failure"], ["9:45", "Loading the data"],
  ["10:35", "Proof it works"], ["11:05", "Recap & sign-off"],
];

function rundownTable() {
  const colA = 1600, colB = CONTENT_W - 1600;
  const headerRow = new TableRow({
    tableHeader: true,
    children: [
      new TableCell({
        width: { size: colA, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: INK },
        margins: { top: 90, bottom: 90, left: 160, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: "TIMECODE", bold: true, color: "FFFFFF", font: F_HEAD, size: 15, allCaps: true, characterSpacing: 16 })] })],
      }),
      new TableCell({
        width: { size: colB, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: INK },
        margins: { top: 90, bottom: 90, left: 160, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: "SCENE", bold: true, color: "FFFFFF", font: F_HEAD, size: 15, allCaps: true, characterSpacing: 16 })] })],
      }),
    ],
  });
  const rows = rundown.map(([tc, title], i) =>
    new TableRow({
      children: [
        new TableCell({
          width: { size: colA, type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, fill: i % 2 === 0 ? "FFFFFF" : "F3F5F8" },
          margins: { top: 80, bottom: 80, left: 160, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: tc, font: F_MONO, size: 18, color: FUEL })] })],
        }),
        new TableCell({
          width: { size: colB, type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, fill: i % 2 === 0 ? "FFFFFF" : "F3F5F8" },
          margins: { top: 80, bottom: 80, left: 160, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: `Scene ${i}. ${title}`, font: F_BODY, size: 20, color: INK })] })],
        }),
      ],
    })
  );
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [colA, colB],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color: LINE }, bottom: { style: BorderStyle.SINGLE, size: 2, color: LINE },
      left: { style: BorderStyle.SINGLE, size: 2, color: LINE }, right: { style: BorderStyle.SINGLE, size: 2, color: LINE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: LINE }, insideVertical: { style: BorderStyle.SINGLE, size: 2, color: LINE },
    },
    rows: [headerRow, ...rows],
  });
}

function footerTable() {
  const rowsData = [
    ["Total runtime", "~11:45"],
    ["Record", "Screen capture, editor + terminal split, 1080p60"],
    ["Before rolling", "python manage.py runserver already up; DB pre-loaded via load_fuel_stations"],
    ["Files to have open", "settings.py, models.py, serializers.py, views.py, geocoding.py, routing_client.py, fuel_optimizer.py, exceptions.py, load_fuel_stations.py"],
  ];
  const colA = 2200, colB = CONTENT_W - 2200;
  const rows = rowsData.map(([k, v], i) =>
    new TableRow({
      children: [
        new TableCell({
          width: { size: colA, type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, fill: i % 2 === 0 ? "FFFFFF" : "F3F5F8" },
          margins: { top: 90, bottom: 90, left: 160, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: k, bold: true, font: F_HEAD, size: 18, color: INK_FAINT, allCaps: true, characterSpacing: 10 })] })],
        }),
        new TableCell({
          width: { size: colB, type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, fill: i % 2 === 0 ? "FFFFFF" : "F3F5F8" },
          margins: { top: 90, bottom: 90, left: 160, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: v, font: F_MONO, size: 18, color: INK })] })],
        }),
      ],
    })
  );
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [colA, colB],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color: LINE }, bottom: { style: BorderStyle.SINGLE, size: 2, color: LINE },
      left: { style: BorderStyle.SINGLE, size: 2, color: LINE }, right: { style: BorderStyle.SINGLE, size: 2, color: LINE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: LINE }, insideVertical: { style: BorderStyle.SINGLE, size: 2, color: LINE },
    },
    rows,
  });
}

// ---------- scenes ----------
const scenes = [];

scenes.push({
  num: "0", title: "Cold open — the receipt, before the code", tc: "0:00",
  file: "terminal", isSpecial: true,
  code: [
    "$ curl -X POST http://127.0.0.1:8000/api/v1/route/ \\",
    '  -H "Content-Type: application/json" \\',
    "  -d '{\"start\": \"Los Angeles, CA\", \"finish\": \"New York, NY\"}'",
    "",
    { text: '{ "distance_miles": 2789.3, "total_fuel_stops": 11,', comment: true },
    { text: '  "total_gallons_purchased": 228.925,', comment: true },
    { text: '  "total_fuel_cost_usd": 696.86, ... }', comment: true },
  ],
  action: "Let it sit for a beat. Don't explain it yet.",
  narration: [
    { beat: "SAY", text: "One HTTP request. Two cities, three thousand miles apart. And it comes back with an actual answer: drive 2,789 miles, stop eleven times, buy 229 gallons, spend $696.86 — and it'll tell you exactly which truck stops, in order." },
    { text: "That number didn't come from a lookup table. Something computed it. Let's open the hood." },
  ],
});

scenes.push({
  num: "1", title: "The one-sentence premise", tc: "0:25", file: "README.md",
  code: [
    { text: "# Fuel Route API", comment: true },
    "",
    "A Django REST API that, given a start and finish",
    "location, returns a driving route, the cheapest",
    "sequence of fuel stops (given a 500-mile range),",
    "and the total projected fuel cost at 10 MPG.",
  ],
  narration: [
    { beat: "SAY", text: "It's a Django REST Framework project, one app called routing, one endpoint. Everything we're about to look at exists to answer one question well: where should this vehicle stop, and how much should it buy each time, to spend the least money getting there?" },
  ],
});

scenes.push({
  num: "2", title: "The project skeleton", tc: "0:50", file: "fuel_route_api/settings.py · urls.py",
  code: [
    'VEHICLE_RANGE_MILES = float(os.environ.get("VEHICLE_RANGE_MILES", 500))',
    'VEHICLE_MPG          = float(os.environ.get("VEHICLE_MPG", 10))',
    'ROUTE_CORRIDOR_MILES = float(os.environ.get("ROUTE_CORRIDOR_MILES", 12))',
  ],
  action: 'Cut to routing/urls.py — one line: path("route/", RoutePlanView.as_view())',
  narration: [
    { beat: "SAY", text: "Three numbers run this whole app: a 500-mile tank range, 10 miles per gallon, and a 12-mile-wide \"corridor\" — how far off the highway a station can sit and still count as being on the route. Change these in .env, nothing else moves." },
    { text: "And routing-wise, there's exactly one door in: POST /api/v1/route/." },
  ],
});

scenes.push({
  num: "3", title: "The data model — one table", tc: "1:35", file: "routing/models.py",
  code: [
    "class FuelStation(models.Model):",
    "    name             = models.CharField(max_length=255)",
    "    city, state      = ...",
    "    price_per_gallon = models.DecimalField(max_digits=8, decimal_places=5)",
    "    latitude, longitude = models.FloatField(null=True, db_index=True)",
    "    geocoded         = models.BooleanField(default=False)",
  ],
  narration: [
    { beat: "SAY", text: "The entire database is one table: 8,151 truck stops, each with a price per gallon and a coordinate. That's it. latitude/longitude are indexed, because in a minute we're going to filter this table geographically, fast." },
  ],
});

scenes.push({
  num: "4", title: "The contract at the door", tc: "2:20", file: "routing/serializers.py",
  code: [
    "def validate(self, attrs):",
    '    if attrs["start"].strip().lower() == attrs["finish"].strip().lower():',
    "        raise serializers.ValidationError(",
    '            "`start` and `finish` must be different locations.")',
  ],
  narration: [
    { beat: "SAY", text: "Before any of the real work happens, DRF's serializer checks the shape of the request — is start a string, is range_miles a positive number — and this one custom rule: you can't route somewhere to itself. Fails here, and it's a clean 400, no wasted API calls downstream." },
  ],
});

scenes.push({
  num: "5", title: "The orchestrator — six steps, no logic of its own", tc: "3:05", file: "routing/views.py",
  code: [
    "cached_response = cache.get(plan_key)",
    "if cached_response is not None:",
    "    return Response(cached_response)   # repeat trip = instant",
    "",
    'start_geo  = geocoding.geocode_address(data["start"])',
    'finish_geo = geocoding.geocode_address(data["finish"])',
    "route      = routing_client.get_route(...)",
    'polyline   = fuel_optimizer.RoutePolyline.from_geometry(route["geometry"])',
    "matched    = fuel_optimizer.match_stations_to_route(stations_qs, polyline, ...)",
    "plan       = fuel_optimizer.plan_fuel_stops(matched_stations=matched, ...)",
  ],
  action: "Scroll slowly — let the reader see it's a straight line, not a maze.",
  narration: [
    { beat: "SAY", text: "RoutePlanView.post() doesn't compute anything itself — it's a conductor. Check the cache. Geocode start and finish. Get one route from OSRM. Hand the route's shape and every station in the DB to the optimizer. Build a map link. Return JSON." },
    { text: "Every one of those six lines is a different file, and that's deliberate — each piece is independently testable." },
  ],
});

scenes.push({
  num: "6", title: 'Turning "Chicago, IL" into a coordinate', tc: "4:30", file: "routing/services/geocoding.py",
  code: [
    "def _throttle():",
    "    elapsed = time.monotonic() - _last_request_at",
    "    if elapsed < settings.NOMINATIM_MIN_INTERVAL_SECONDS:",
    "        time.sleep(...)   # never exceed 1 req/sec",
    "",
    'cache_key = f"geocode:{normalized}"',
    "if (cached := cache.get(cache_key)): return cached",
  ],
  narration: [
    { beat: "SAY", text: "This is a thin wrapper around Nominatim, OpenStreetMap's free geocoder. Two things matter here: it's throttled to respect their one-request-per-second policy, and every result is cached — ask for \"Chicago, IL\" twice, the second time costs zero network calls." },
  ],
});

scenes.push({
  num: "7", title: "One call to the road", tc: "5:20", file: "routing/services/routing_client.py",
  code: [
    'url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{coords}"',
    "response = requests.get(url, params={",
    '    "overview": "full", "geometries": "geojson"',
    "})",
  ],
  narration: [
    { beat: "SAY", text: "OSRM — the actual road-routing engine — gets called exactly once per trip. One request returns the full driving path as a list of coordinates, plus distance and duration. That single-call discipline is why this API stays fast." },
  ],
});

scenes.push({
  num: "8", title: "The brain, part one: which stations are actually on the way", tc: "5:50",
  file: "routing/services/fuel_optimizer.py · lines 95–158",
  code: [
    { text: "# pass 1: cheap DB bounding-box query (uses the lat/lon index)", comment: true },
    "stations_qs.filter(latitude__gte=..., latitude__lte=...)",
    "",
    { text: "# pass 2: precise numpy distance, station × every route point", comment: true },
    "distances = haversine_miles(station_lat[:, None], station_lon[:, None],",
    "                             polyline.lat[None, :], polyline.lon[None, :])",
    "nearest_point_idx = np.argmin(distances, axis=1)",
  ],
  action: "Whiteboard cutaway: draw the route as a line, a dot 12 miles off it inside a shaded band, a dot 40 miles off outside it.",
  narration: [
    { beat: "SAY", text: "Out of 8,151 stations, which ones are actually near this route? Two passes: a cheap SQL bounding-box first, to throw out the obviously-too-far ones using the database index. Then a precise pass — numpy checks every remaining candidate against every point on the route's shape, all at once, vectorized. Anything outside that 12-mile corridor gets dropped." },
    { text: "What's left, each station also gets tagged with a mile-marker: how far along the trip it sits." },
  ],
});

scenes.push({
  num: "9", title: "The brain, part two: the greedy fuel algorithm", tc: "7:10",
  file: "routing/services/fuel_optimizer.py · plan_fuel_stops(), lines 178–304",
  code: [
    "cheapest_in_window = min(window, key=lambda s: s.price_per_gallon)",
    "",
    "if cheapest_in_window.price_per_gallon < current_price:",
    { text: "    # cheaper station ahead → buy just enough gas to reach it", comment: true },
    "elif destination_reachable:",
    { text: "    # nothing cheaper ahead, and we can finish from here → stop", comment: true },
    "else:",
    { text: "    # nothing cheaper in reach → fill the tank completely", comment: true },
  ],
  action: "This is the longest scene — slow down here. Consider a hand-drawn overlay: a car icon, a dashed \"full tank\" circle around it, price tags at two stations inside the circle.",
  narration: [
    { beat: "SAY", text: "Here's the actual strategy, in plain terms. Standing at any point with fuel in the tank, look at every station you could reach without running dry." },
    { text: "See something cheaper ahead? Buy just enough right now to limp there — don't overpay at the expensive stop. See nothing cheaper within reach? That means this is the best price you'll get before you'd run out of range — so fill up completely, here, now." },
    { text: "Repeat that until the destination itself is within reach of a full tank. It sounds almost too simple — but for this exact problem — buy any fraction of a gallon, one tank size, prices vary by stop — this greedy rule is provably the cheapest possible plan. It's proven with worked examples in test_fuel_optimizer.py." },
  ],
});

scenes.push({
  num: "10", title: "Failing cleanly", tc: "9:15", file: "routing/exceptions.py",
  code: [
    "class RouteInfeasibleError(FuelRouteError):",
    '    default_message = ("No feasible fuel plan exists for this route...")',
    "    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY",
  ],
  narration: [
    { beat: "SAY", text: "Three named failure modes — can't geocode a place, OSRM can't route it, or a stretch of road is longer than the vehicle's range with nothing to refuel at. Each one carries its own HTTP status. One handler turns any of them into a clean {\"error\": \"...\"} instead of a stack trace leaking out." },
  ],
});

scenes.push({
  num: "11", title: "Getting 8,151 stations into the table", tc: "9:45",
  file: "routing/management/commands/load_fuel_stations.py",
  code: [
    "$ python manage.py load_fuel_stations --clear",
    "Cleared 8151 existing rows.",
    "Loaded 8151 stations (8151 with coordinates).",
    "",
    { text: "real  0m1.842s", comment: true },
  ],
  narration: [
    { beat: "SAY", text: "This one's offline, separate from the API entirely — it reads a spreadsheet that already has latitude and longitude for every station, and bulk-inserts it. No geocoding, no external calls, done in under two seconds." },
    { text: "That matters more than it sounds — an earlier version of this command geocoded every station live, one request per city at a time, and a free public geocoder rate-limits that hard. Shipping the coordinates with the data sidesteps the whole problem." },
  ],
});

scenes.push({
  num: "12", title: "Proof it works", tc: "10:35", file: "routing/tests/",
  code: [
    "$ python manage.py test routing",
    "............",
    "Ran 12 tests in 0.031s",
    "",
    "OK",
  ],
  narration: [
    { beat: "SAY", text: "Three test files, three layers: the greedy algorithm's decisions in isolation — does it correctly detour for a cheaper station, does it fill up when nothing's cheaper. The corridor matching against a real test database. And the whole endpoint, end to end, with the external services mocked out — so the suite runs in thirty milliseconds, no network required." },
  ],
});

scenes.push({
  num: "13", title: "Recap & sign-off", tc: "11:05", file: "terminal", isSpecial: true,
  code: [
    "Maverik #674           North Las Vegas NV  $3.282  mile 295   29.5gal",
    "AKAL TRAVEL CENTER     Waco NE             $2.799  mile 1456  50.0gal",
    "SHEETZ #639            Youngstown OH       $3.059  mile 2400   5.4gal",
  ],
  narration: [
    { beat: "SAY", text: "Six files, one request: geocode, route once, filter 8,000 stations down to the ones on the road, then a greedy rule that's provably the cheapest way to buy gas along it. That's the whole system." },
    { text: "Code's linked below. Thanks for watching." },
  ],
});

// ---------- assemble document ----------
const children = [];

children.push(eyebrow("Shooting Script  ·  Code Walkthrough"));
children.push(new Paragraph({
  heading: HeadingLevel.TITLE,
  spacing: { after: 160 },
  children: [new TextRun({ text: "Fuel Route API", bold: true, font: F_HEAD, size: 52, color: INK })],
}));
children.push(new Paragraph({
  spacing: { after: 160 },
  children: [new TextRun({ text: "How it decides where to stop for gas", font: F_HEAD, size: 30, color: ROUTE })],
}));
children.push(new Paragraph({
  spacing: { after: 100 },
  children: [new TextRun({
    text: "A scene-by-scene script for a screen-capture video: what to have on screen, and what to say over it, file by file, from the first HTTP request down to the greedy algorithm that picks the fuel stops.",
    font: F_BODY, size: 22, color: INK_SOFT,
  })],
}));
children.push(new Paragraph({
  spacing: { after: 60 },
  children: [new TextRun({
    text: "Runtime ~11:45   ·   14 scenes   ·   11 files on screen   ·   manage.py runserver",
    font: F_MONO, size: 17, color: INK_FAINT,
  })],
}));
children.push(hr());

children.push(calloutBox([
  { label: "How to shoot this:", text: "one take, screen-recorded. The ON SCREEN block is what's in frame — a file open in your editor, or a terminal. The NARRATION lines are spoken live over it, not read verbatim — use them as talking points." },
  { text: "Every number and API response quoted here is a real run of this codebase, not a mock-up." },
], "F3F5F8", INK_SOFT));

children.push(new Paragraph({ spacing: { before: 320, after: 140 }, heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: "Rundown", bold: true, font: F_HEAD, size: 26, color: INK })] }));
children.push(rundownTable());

children.push(new Paragraph({ pageBreakBefore: true, spacing: { after: 0 }, heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: "Script", bold: true, font: F_HEAD, size: 26, color: INK })] }));

for (const s of scenes) {
  children.push(...sceneHeading(s.num, s.title, s.tc, s.file));
  children.push(colLabel("On screen"));
  children.push(codeBlock(s.code));
  if (s.action) children.push(actionNote(s.action));
  children.push(colLabel("Narration"));
  children.push(...narrationParas(s.narration));
}

children.push(new Paragraph({ pageBreakBefore: true, spacing: { after: 140 }, heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: "Production Notes", bold: true, font: F_HEAD, size: 26, color: INK })] }));
children.push(footerTable());
children.push(new Paragraph({
  spacing: { before: 160 },
  children: [new TextRun({
    text: "All API responses and terminal output in this script are real, captured runs of this codebase — none of it is illustrative or mocked up for the video.",
    italics: true, font: F_BODY, size: 18, color: INK_FAINT,
  })],
}));

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: F_BODY, size: 21, color: INK } },
    },
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN },
        },
      },
      children,
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("Fuel-Route-API-Shooting-Script.docx", buf);
  console.log("written");
});
