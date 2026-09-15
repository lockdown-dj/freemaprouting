"""
Thin client for OpenStreetMap's Nominatim geocoding service (free, keyless).

Used once per request to resolve the user-supplied `start` and `finish`
locations to lat/lon (results cached via Django's cache framework, so a
repeated query never re-hits the API).

Nominatim's usage policy caps unauthenticated use at 1 request/second and
requires a descriptive User-Agent -- both are respected here.
"""

import logging
import time

import requests
from django.conf import settings
from django.core.cache import cache

from routing.exceptions import GeocodingError

logger = logging.getLogger(__name__)

_last_request_at = 0.0


def _throttle():
    global _last_request_at
    min_interval = settings.NOMINATIM_MIN_INTERVAL_SECONDS
    elapsed = time.monotonic() - _last_request_at
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request_at = time.monotonic()


def _headers():
    return {"User-Agent": settings.NOMINATIM_USER_AGENT}


def geocode_address(query: str) -> dict:
    """
    Geocode a free-form address/place string (e.g. "Chicago, IL" or
    "1600 Amphitheatre Parkway, Mountain View, CA") to a lat/lon.

    Cached per normalized query for GEOCODE_CACHE_TTL seconds so repeated
    API requests with the same start/finish never re-hit Nominatim.
    """
    normalized = " ".join(query.strip().lower().split())
    cache_key = f"geocode:{normalized}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    _throttle()
    try:
        response = requests.get(
            f"{settings.NOMINATIM_BASE_URL}/search",
            params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
            headers=_headers(),
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Geocoding request failed for %r: %s", query, exc)
        raise GeocodingError(
            f"Geocoding service error while resolving '{query}': {exc}"
        ) from exc

    if not results:
        raise GeocodingError(f"Could not find a location matching '{query}'.")

    top = results[0]
    result = {
        "latitude": float(top["lat"]),
        "longitude": float(top["lon"]),
        "display_name": top.get("display_name", query),
    }
    cache.set(cache_key, result, settings.GEOCODE_CACHE_TTL)
    return result
