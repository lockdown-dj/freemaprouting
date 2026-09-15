"""
Django settings for the fuel_route_api project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = _env_bool("DEBUG", True)
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", "127.0.0.1,localhost")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "routing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "fuel_route_api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "fuel_route_api.wsgi.application"
ASGI_APPLICATION = "fuel_route_api.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "routing.exceptions.fuel_route_exception_handler",
}

# ---------------------------------------------------------------------------
# Caching. Speeds up repeat requests (same start/finish pair) considerably,
# and avoids re-hitting the geocoding / routing APIs. Swap BACKEND for
# django.core.cache.backends.redis.RedisCache in production/multi-process
# deployments; LocMemCache is fine for local dev and this assessment.
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fuel-route-api-cache",
    }
}

# ---------------------------------------------------------------------------
# Domain configuration
# ---------------------------------------------------------------------------
VEHICLE_RANGE_MILES = float(os.environ.get("VEHICLE_RANGE_MILES", 500))
VEHICLE_MPG = float(os.environ.get("VEHICLE_MPG", 10))
ROUTE_CORRIDOR_MILES = float(os.environ.get("ROUTE_CORRIDOR_MILES", 12))

NOMINATIM_BASE_URL = os.environ.get("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
NOMINATIM_USER_AGENT = os.environ.get(
    "NOMINATIM_USER_AGENT", "fuel-route-api-be-assessment (contact: you@example.com)"
)
# Minimum gap between outgoing Nominatim requests, per their usage policy.
NOMINATIM_MIN_INTERVAL_SECONDS = float(os.environ.get("NOMINATIM_MIN_INTERVAL_SECONDS", 1.0))
OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")

GEOCODE_CACHE_TTL = int(os.environ.get("GEOCODE_CACHE_TTL", 60 * 60 * 24 * 30))
ROUTE_CACHE_TTL = int(os.environ.get("ROUTE_CACHE_TTL", 60 * 60 * 24))
PLAN_CACHE_TTL = int(os.environ.get("PLAN_CACHE_TTL", 60 * 60 * 24))

# Path used by default when running `manage.py load_fuel_stations` with no args.
# This file already has Latitude/Longitude columns, so the load is a plain
# import -- no geocoding needed.
FUEL_PRICES_XLSX_PATH = BASE_DIR / "data" / "fuel_prices_with_coords.xlsx"
