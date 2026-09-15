from django.conf import settings
from rest_framework import serializers


class RoutePlanRequestSerializer(serializers.Serializer):
    start = serializers.CharField(
        max_length=255, help_text="Start location, e.g. 'Los Angeles, CA' or a full address."
    )
    finish = serializers.CharField(
        max_length=255, help_text="Finish location, e.g. 'New York, NY' or a full address."
    )
    range_miles = serializers.FloatField(
        required=False, default=settings.VEHICLE_RANGE_MILES, min_value=1,
        help_text="Max distance (miles) the vehicle can travel on a full tank.",
    )
    mpg = serializers.FloatField(
        required=False, default=settings.VEHICLE_MPG, min_value=0.1,
        help_text="Vehicle fuel economy in miles per gallon.",
    )

    def validate(self, attrs):
        if attrs["start"].strip().lower() == attrs["finish"].strip().lower():
            raise serializers.ValidationError("`start` and `finish` must be different locations.")
        return attrs


class LocationSerializer(serializers.Serializer):
    query = serializers.CharField()
    display_name = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class FuelStopSerializer(serializers.Serializer):
    name = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    address = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    price_per_gallon = serializers.FloatField()
    position_along_route_miles = serializers.FloatField()
    distance_from_route_miles = serializers.FloatField()
    gallons_purchased = serializers.FloatField()
    cost = serializers.FloatField()


class RoutePlanResponseSerializer(serializers.Serializer):
    start = LocationSerializer()
    finish = LocationSerializer()
    distance_miles = serializers.FloatField()
    duration_hours = serializers.FloatField()
    vehicle = serializers.DictField()
    route_geometry = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2)
    )
    map_image_url = serializers.URLField()
    fuel_stops = FuelStopSerializer(many=True)
    total_fuel_stops = serializers.IntegerField()
    total_gallons_purchased = serializers.FloatField()
    total_fuel_cost_usd = serializers.FloatField()
    assumptions = serializers.ListField(child=serializers.CharField())
