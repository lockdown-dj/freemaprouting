from django.contrib import admin

from .models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "state", "price_per_gallon", "geocoded", "latitude", "longitude")
    list_filter = ("state", "geocoded")
    search_fields = ("name", "city", "state", "address")
