"""
Load fuel station prices + coordinates from the supplied xlsx into the DB.

The source file already has Latitude/Longitude columns, so this is a plain
bulk import -- no geocoding, no rate limits, no network calls.

Usage:
    python manage.py load_fuel_stations                 # uses data/fuel_prices_with_coords.xlsx
    python manage.py load_fuel_stations path/to/other.xlsx
    python manage.py load_fuel_stations --limit 200      # only load the first N rows (smoke test)
    python manage.py load_fuel_stations --clear          # wipe existing rows first
"""

import openpyxl
from django.conf import settings
from django.core.management.base import BaseCommand

from routing.models import FuelStation


class Command(BaseCommand):
    help = "Load fuel station prices + coordinates from an xlsx file."

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", nargs="?", default=None)
        parser.add_argument("--limit", type=int, default=None, help="Only load the first N rows.")
        parser.add_argument(
            "--clear", action="store_true", help="Delete all existing FuelStation rows before loading.",
        )

    def handle(self, *args, xlsx_path, limit, clear, **options):
        xlsx_path = xlsx_path or settings.FUEL_PRICES_XLSX_PATH

        if clear:
            deleted, _ = FuelStation.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing rows.")

        wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        rows = wb.active.iter_rows(values_only=True)
        header = [str(c).strip() for c in next(rows)]

        def col(name):
            return header.index(name)

        stations = []
        for row in rows:
            if limit and len(stations) >= limit:
                break

            latitude = row[col("Latitude")]
            longitude = row[col("Longitude")]

            stations.append(
                FuelStation(
                    opis_truckstop_id=int(row[col("OPIS Truckstop ID")]),
                    name=str(row[col("Truckstop Name")]).strip(),
                    address=str(row[col("Address")] or "").strip(),
                    city=str(row[col("City")]).strip(),
                    state=str(row[col("State")]).strip(),
                    rack_id=str(row[col("Rack ID")]),
                    price_per_gallon=row[col("Retail Price")],
                    latitude=latitude,
                    longitude=longitude,
                    geocoded=latitude is not None and longitude is not None,
                )
            )

        FuelStation.objects.bulk_create(stations, batch_size=500)

        geocoded_count = sum(1 for s in stations if s.geocoded)
        self.stdout.write(
            self.style.SUCCESS(f"Loaded {len(stations)} stations ({geocoded_count} with coordinates).")
        )
