from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class FuelRouteError(Exception):
    """Base class for all domain errors raised by the routing app."""

    default_message = "An unexpected error occurred."
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message=None):
        self.message = message or self.default_message
        super().__init__(self.message)


class GeocodingError(FuelRouteError):
    default_message = "Could not resolve one of the supplied locations to a map coordinate."
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class RoutingError(FuelRouteError):
    default_message = "Could not compute a driving route between the supplied locations."
    status_code = status.HTTP_502_BAD_GATEWAY


class RouteInfeasibleError(FuelRouteError):
    default_message = (
        "No feasible fuel plan exists for this route: a stretch of the route exceeds the "
        "vehicle's range with no fuel station reachable along the way."
    )
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


def fuel_route_exception_handler(exc, context):
    """
    DRF exception handler: turns FuelRouteError subclasses into clean JSON
    error responses, and falls back to DRF's default handling for
    everything else (validation errors, 404s, etc.).
    """
    if isinstance(exc, FuelRouteError):
        return Response({"error": exc.message}, status=exc.status_code)

    return exception_handler(exc, context)
