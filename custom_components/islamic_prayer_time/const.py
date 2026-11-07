"""Constants for the Islamic Prayer Time integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "islamic_prayer_time"
NAME: Final = "Islamic Prayer Time"
VERSION: Final = "1.0.0"

# ---------------------------------------------------------------------------
# Config / option keys
# ---------------------------------------------------------------------------
CONF_CALC_METHOD: Final = "calculation_method"
CONF_SCHOOL: Final = "school"
CONF_LAT_ADJ_METHOD: Final = "latitude_adjustment_method"
CONF_MIDNIGHT_MODE: Final = "midnight_mode"

CONF_USE_HOME_LOCATION: Final = "use_home_location"
CONF_USE_HOME_ELEVATION: Final = "use_home_elevation"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_ELEVATION: Final = "elevation"

CONF_HIJRI_OFFSET: Final = "hijri_offset"
CONF_OFFSET_PREFIX: Final = "offset_"

# ---------------------------------------------------------------------------
# Calculation settings
#
# The defaults mirror the Home Assistant core `islamic_prayer_times`
# integration exactly (same library, same method names, same defaults), so a
# fresh install produces identical times to the core integration.
# ---------------------------------------------------------------------------
CALC_METHODS: Final[list[str]] = [
    "karachi",
    "mwl",
    "isna",
    "egypt",
    "makkah",
    "gulf",
    "kuwait",
    "qatar",
    "dubai",
    "singapore",
    "jakim",
    "kemenag",
    "turkey",
    "russia",
    "france",
    "tunisia",
    "algeria",
    "morocco",
    "portugal",
    "jordan",
    "tehran",
    "jafari",
    "moonsighting",
]
DEFAULT_CALC_METHOD: Final = "karachi"

SCHOOLS: Final[list[str]] = ["shafi", "hanafi"]
DEFAULT_SCHOOL: Final = "shafi"

LAT_ADJ_METHODS: Final[list[str]] = [
    "middle_of_the_night",
    "one_seventh",
    "angle_based",
]
DEFAULT_LAT_ADJ_METHOD: Final = "middle_of_the_night"

MIDNIGHT_MODES: Final[list[str]] = ["standard", "jafari"]
DEFAULT_MIDNIGHT_MODE: Final = "standard"

DEFAULT_HIJRI_OFFSET: Final = 0
HIJRI_OFFSET_RANGE: Final = (-2, 2)

# ---------------------------------------------------------------------------
# Prayers
# ---------------------------------------------------------------------------
# The six times shown on dashboards, in chronological order.
PRAYERS: Final[list[str]] = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]

# Extra times exposed as (disabled-by-default) sensors.
EXTRA_TIMES: Final[list[str]] = ["imsak", "midnight", "last_third"]

# Everything that can carry a minute offset.
ADJUSTABLE_TIMES: Final[list[str]] = [*PRAYERS, "imsak", "midnight"]

OFFSET_RANGE: Final = (-60, 60)

# Map from our keys to the keys returned by prayer_times_calculator_offline.
LIBRARY_KEYS: Final[dict[str, str]] = {
    "imsak": "Imsak",
    "fajr": "Fajr",
    "sunrise": "Sunrise",
    "dhuhr": "Dhuhr",
    "asr": "Asr",
    "maghrib": "Maghrib",
    "isha": "Isha",
    "midnight": "Midnight",
    "last_third": "Lastthird",
}

PRAYER_ICONS: Final[dict[str, str]] = {
    "imsak": "mdi:food-off-outline",
    "fajr": "mdi:weather-night-partly-cloudy",
    "sunrise": "mdi:weather-sunset-up",
    "dhuhr": "mdi:white-balance-sunny",
    "asr": "mdi:weather-partly-cloudy",
    "maghrib": "mdi:weather-sunset-down",
    "isha": "mdi:weather-night",
    "midnight": "mdi:moon-waning-crescent",
    "last_third": "mdi:star-crescent",
}

# Bus event fired when a prayer time is reached.
EVENT_PRAYER_TIME: Final = f"{DOMAIN}_prayer"

# Frontend
FRONTEND_URL_BASE: Final = f"/{DOMAIN}"
FRONTEND_CARDS_FILE: Final = "islamic-prayer-time-cards.js"
