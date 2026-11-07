"""Integration tests: config flow, setup, entities, live offset changes."""

from __future__ import annotations

from datetime import timedelta

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.islamic_prayer_time.const import DOMAIN


@pytest.fixture(autouse=True)
async def _enable(enable_custom_integrations, hass: HomeAssistant) -> None:
    hass.config.latitude = 21.4225
    hass.config.longitude = 39.8262
    hass.config.elevation = 277
    await hass.config.async_set_time_zone("Asia/Riyadh")


async def test_config_flow_home_location(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Masjid",
            "calculation_method": "karachi",
            "school": "shafi",
            "latitude_adjustment_method": "middle_of_the_night",
            "midnight_mode": "standard",
            "use_home_location": True,
            "use_home_elevation": False,
        },
    )
    assert result["step_id"] == "offsets"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "offset_fajr": -8, "offset_sunrise": 0, "offset_dhuhr": 2,
            "offset_asr": 3, "offset_maghrib": 3, "offset_isha": 3,
            "offset_imsak": 0, "offset_midnight": 0, "hijri_offset": 0,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Masjid"
    assert result["options"]["offset_fajr"] == -8
    await hass.async_block_till_done()
    assert hass.states.get("sensor.masjid_fajr") is not None


async def test_config_flow_custom_location(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "London",
            "calculation_method": "mwl",
            "school": "hanafi",
            "latitude_adjustment_method": "angle_based",
            "midnight_mode": "standard",
            "use_home_location": False,
            "use_home_elevation": False,
        },
    )
    assert result["step_id"] == "location"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"latitude": 51.5072, "longitude": -0.1276, "elevation": 11}
    )
    assert result["step_id"] == "offsets"


async def _setup(hass: HomeAssistant, **options) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Prayer Times", data={}, options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities_and_live_offset(hass: HomeAssistant) -> None:
    entry = await _setup(hass, use_home_location=True)
    fajr = hass.states.get("sensor.prayer_times_fajr")
    assert fajr is not None and fajr.attributes["offset_minutes"] == 0
    assert hass.states.get("sensor.prayer_times_current_prayer").state in (
        "fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"
    )
    assert hass.states.get("sensor.prayer_times_hijri_date").state.endswith("AH")

    before = fajr.state
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.prayer_times_fajr_offset", "value": -8},
        blocking=True,
    )
    await hass.async_block_till_done()
    after = hass.states.get("sensor.prayer_times_fajr")
    from homeassistant.util import dt as dt_util

    assert dt_util.parse_datetime(before) - dt_util.parse_datetime(after.state) == timedelta(minutes=8)
    assert entry.options["offset_fajr"] == -8


async def test_change_method_from_select(hass: HomeAssistant) -> None:
    await _setup(hass)
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": "select.prayer_times_calculation_method", "option": "isna"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("select.prayer_times_calculation_method").state == "isna"


async def test_extra_sensors_disabled_by_default(hass: HomeAssistant) -> None:
    await _setup(hass)
    reg = er.async_get(hass)
    imsak = reg.async_get("sensor.prayer_times_imsak")
    assert imsak is not None and imsak.disabled_by is not None


async def test_unload(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
