from django.db import models


class FuelStation(models.Model):
    """
    A single truck-stop / fuel-station price record, loaded from the
    OPIS fuel price CSV and enriched with an approximate lat/lon obtained
    once (at data-load time) via geocoding of the station's city & state.

    Coordinates are city-level, not exact-address-level, since the source
    "Address" column is a highway/exit description (e.g. "I-44, EXIT 283")
    rather than a geocodable street address. That's precise enough to match
    stations to a driving corridor a few miles wide, which is what the
    fuel-stop optimizer needs.
    """

    opis_truckstop_id = models.IntegerField(db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=128)
    state = models.CharField(max_length=8)
    rack_id = models.CharField(max_length=32, blank=True)
    price_per_gallon = models.DecimalField(max_digits=8, decimal_places=5)

    latitude = models.FloatField(null=True, blank=True, db_index=True)
    longitude = models.FloatField(null=True, blank=True, db_index=True)
    geocoded = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["city", "state"]),
        ]
        ordering = ["price_per_gallon"]

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state}) - ${self.price_per_gallon}/gal"
