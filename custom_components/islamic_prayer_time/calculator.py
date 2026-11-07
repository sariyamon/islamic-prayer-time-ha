"""Pure prayer-time calculation layer.

This module has no Home Assistant dependency so it can be unit tested on its
own. It wraps `prayer_times_calculator_offline` – the exact library used by the
Home Assistant core `islamic_prayer_times` integration – and adds:

* observer elevation (affects sunrise / maghrib),
* per-prayer minute offsets (the "tune" values),
* current / next prayer resolution,
* a Hijri date with a +/- day adjustment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from prayer_times_calculator_offline import PrayerTimesCalculator
from prayer_times_calculator_offline.praytimes import PrayTimes

from .const import ADJUSTABLE_TIMES, LIBRARY_KEYS, PRAYERS

HIJRI_MONTHS_EN = [
    "Muharram",
    "Safar",
    "Rabi al-Awwal",
    "Rabi al-Thani",
    "Jumada al-Ula",
    "Jumada al-Akhirah",
    "Rajab",
    "Shaban",
    "Ramadan",
    "Shawwal",
    "Dhu al-Qadah",
    "Dhu al-Hijjah",
]
HIJRI_MONTHS_AR = [
    "مُحَرَّم",
    "صَفَر",
    "رَبيع الأوّل",
    "رَبيع الثاني",
    "جُمادى الأولى",
    "جُمادى الآخرة",
    "رَجَب",
    "شَعْبان",
    "رَمَضان",
    "شَوّال",
    "ذو القعدة",
    "ذو الحجة",
]


@dataclass(frozen=True)
class CalcSettings:
    """Everything that influences the calculation."""

    latitude: float
    longitude: float
    elevation: float = 0.0
    method: str = "karachi"
    school: str = "shafi"
    lat_adjustment: str = "middle_of_the_night"
    midnight_mode: str = "standard"
    offsets: dict[str, int] = field(default_factory=dict)
    hijri_offset: int = 0


@dataclass
class DayTimes:
    """Prayer times for one calendar day (all values timezone-aware UTC)."""

    day: date
    calculated: dict[str, datetime]
    adjusted: dict[str, datetime]
    hijri: dict[str, Any]


class _ElevationAwareCalculator(PrayerTimesCalculator):
    """Same calculator as HA core, but passes the observer elevation through."""

    def __init__(self, *args: Any, elevation: float = 0.0, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._elevation = float(elevation or 0.0)

    def fetch_prayer_times(self) -> dict[str, Any]:  # noqa: D102
        calculator = PrayTimes()
        calculator.adjust(self._calculation_parameters)
        if len(self._tune):
            calculator.offset.update(self._tune)

        coords = (self._latitude, self._longitude, self._elevation)
        times_float = calculator.getTimes(self._date, coords, timezone=0, format="Float")

        response: dict[str, Any] = {}
        for key, value in times_float.items():
            stamp = datetime.combine(self._date, time()) + timedelta(hours=value)
            # Round to the nearest minute – identical to the library.
            stamp = (stamp + timedelta(seconds=30) - timedelta.resolution).replace(
                second=0, microsecond=0
            )
            response[key[0].upper() + key[1:]] = stamp.replace(tzinfo=timezone.utc)
        response["date"] = self.computeDateResponse()
        return response


def _library_option(value: str) -> str:
    """Our option values use underscores, the library uses spaces."""
    return value.replace("_", " ")


def calculate_day(settings: CalcSettings, day: date) -> DayTimes:
    """Calculate all times for `day` (a local calendar date)."""
    calc = _ElevationAwareCalculator(
        latitude=settings.latitude,
        longitude=settings.longitude,
        calculation_method=settings.method,
        date=day.isoformat(),
        school=settings.school,
        midnightMode=settings.midnight_mode,
        latitudeAdjustmentMethod=_library_option(settings.lat_adjustment),
        elevation=settings.elevation,
    )
    raw = calc.fetch_prayer_times()

    calculated: dict[str, datetime] = {
        key: raw[lib_key] for key, lib_key in LIBRARY_KEYS.items() if lib_key in raw
    }
    adjusted: dict[str, datetime] = {}
    for key, value in calculated.items():
        minutes = int(settings.offsets.get(key, 0)) if key in ADJUSTABLE_TIMES else 0
        adjusted[key] = value + timedelta(minutes=minutes)

    return DayTimes(
        day=day,
        calculated=calculated,
        adjusted=adjusted,
        hijri=hijri_date(day, settings.hijri_offset),
    )


def hijri_date(day: date, offset_days: int = 0) -> dict[str, Any]:
    """Tabular (Kuwaiti) Hijri date – the algorithm used by Aladhan / HA core."""
    shifted = day + timedelta(days=offset_days)
    calc = PrayerTimesCalculator(0, 0, "karachi", shifted.isoformat())
    year, month, mday = calc.computeHijriDate()
    holidays = calc.computeDateResponse()["hijri"]["holidays"]
    return {
        "day": mday,
        "month": month,
        "year": year,
        "month_name": HIJRI_MONTHS_EN[month - 1],
        "month_name_ar": HIJRI_MONTHS_AR[month - 1],
        "formatted": f"{mday} {HIJRI_MONTHS_EN[month - 1]} {year} AH",
        "holidays": list(dict.fromkeys(holidays)),
    }


def resolve_current_and_next(
    now: datetime, today: DayTimes, tomorrow: DayTimes
) -> tuple[str, str, datetime, datetime]:
    """Return (current, next, current_start, next_start).

    Before today's Fajr the current period is still the previous night's Isha –
    the same behaviour as the dashboard template it replaces.
    """
    current = "isha"
    current_start = today.adjusted["isha"] - timedelta(days=1)
    for prayer in PRAYERS:
        if today.adjusted[prayer] <= now:
            current = prayer
            current_start = today.adjusted[prayer]

    for prayer in PRAYERS:
        if today.adjusted[prayer] > now:
            return current, prayer, current_start, today.adjusted[prayer]
    return current, "fajr", current_start, tomorrow.adjusted["fajr"]
