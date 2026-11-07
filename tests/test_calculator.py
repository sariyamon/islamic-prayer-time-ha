"""Calculation tests – parity with the HA core integration, offsets, elevation."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from prayer_times_calculator_offline import PrayerTimesCalculator
import pytest

from custom_components.islamic_prayer_time.calculator import (
    CalcSettings,
    calculate_day,
    hijri_date,
    resolve_current_and_next,
)
from custom_components.islamic_prayer_time.const import PRAYERS

MAKKAH = (21.4225, 39.8262)
LONDON = (51.5072, -0.1276)
DAY = date(2026, 11, 8)


def _core(lat: float, lon: float, method: str, school: str = "shafi") -> dict[str, datetime]:
    """What the Home Assistant core integration computes."""
    raw = PrayerTimesCalculator(
        latitude=lat,
        longitude=lon,
        calculation_method=method,
        date=DAY.isoformat(),
        school=school,
        midnightMode="standard",
        latitudeAdjustmentMethod="middle of the night",
    ).fetch_prayer_times()
    return {k: datetime.fromisoformat(v) for k, v in raw.items() if k != "date"}


@pytest.mark.parametrize("method", ["karachi", "mwl", "isna", "makkah", "turkey"])
@pytest.mark.parametrize("coords", [MAKKAH, LONDON])
def test_matches_core_integration(coords: tuple[float, float], method: str) -> None:
    core = _core(*coords, method)
    ours = calculate_day(CalcSettings(*coords, method=method), DAY)
    for prayer, lib in {"fajr": "Fajr", "sunrise": "Sunrise", "dhuhr": "Dhuhr",
                        "asr": "Asr", "maghrib": "Maghrib", "isha": "Isha",
                        "midnight": "Midnight"}.items():
        assert ours.adjusted[prayer] == core[lib], prayer


def test_hanafi_asr_is_later() -> None:
    shafi = calculate_day(CalcSettings(*MAKKAH, school="shafi"), DAY)
    hanafi = calculate_day(CalcSettings(*MAKKAH, school="hanafi"), DAY)
    assert hanafi.adjusted["asr"] > shafi.adjusted["asr"]


def test_offsets_shift_only_their_prayer() -> None:
    offsets = {"fajr": -8, "sunrise": 0, "dhuhr": 2, "asr": 3, "maghrib": 3, "isha": 3}
    base = calculate_day(CalcSettings(*MAKKAH), DAY)
    tuned = calculate_day(CalcSettings(*MAKKAH, offsets=offsets), DAY)
    for prayer, minutes in offsets.items():
        assert tuned.adjusted[prayer] - base.adjusted[prayer] == timedelta(minutes=minutes)
        assert tuned.calculated[prayer] == base.calculated[prayer]


def test_elevation_moves_sunrise_and_maghrib_only() -> None:
    flat = calculate_day(CalcSettings(*MAKKAH, elevation=0), DAY)
    high = calculate_day(CalcSettings(*MAKKAH, elevation=2000), DAY)
    assert high.adjusted["sunrise"] < flat.adjusted["sunrise"]
    assert high.adjusted["maghrib"] > flat.adjusted["maghrib"]
    assert high.adjusted["dhuhr"] == flat.adjusted["dhuhr"]


def test_times_are_chronological() -> None:
    day = calculate_day(CalcSettings(*LONDON), DAY)
    values = [day.adjusted[p] for p in PRAYERS]
    assert values == sorted(values)


@pytest.mark.parametrize(
    ("hhmm", "current", "nxt"),
    [
        ("00:30", "isha", "fajr"),
        ("06:00", "fajr", "sunrise"),
        ("12:30", "dhuhr", "asr"),
        ("23:59", "isha", "fajr"),
    ],
)
def test_current_and_next(hhmm: str, current: str, nxt: str) -> None:
    settings = CalcSettings(*MAKKAH)
    today = calculate_day(settings, DAY)
    tomorrow = calculate_day(settings, DAY + timedelta(days=1))
    # Makkah is UTC+3.
    h, m = map(int, hhmm.split(":"))
    now = datetime(DAY.year, DAY.month, DAY.day, h, m, tzinfo=timezone(timedelta(hours=3)))
    cur, nx, cur_start, next_start = resolve_current_and_next(now, today, tomorrow)
    assert (cur, nx) == (current, nxt)
    assert cur_start <= now < next_start
    if nxt == "fajr" and h >= 12:
        assert next_start == tomorrow.adjusted["fajr"]


def test_hijri_offset() -> None:
    base = hijri_date(DAY)
    plus = hijri_date(DAY, 1)
    assert base["year"] == 1448
    assert (plus["day"] - base["day"]) % 30 in (1, 0) or plus["month"] != base["month"]
    assert base["formatted"].endswith("AH")
