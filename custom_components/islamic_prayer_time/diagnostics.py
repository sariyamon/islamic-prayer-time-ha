"""Diagnostics support."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_LATITUDE, CONF_LONGITUDE
from .coordinator import PrayerConfigEntry

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PrayerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics – coordinates are redacted."""
    data = entry.runtime_data.data
    return {
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "settings": async_redact_data(asdict(data.settings), TO_REDACT),
        "today": {k: v.isoformat() for k, v in data.today.adjusted.items()},
        "calculated": {k: v.isoformat() for k, v in data.today.calculated.items()},
        "current": data.current,
        "next": data.next,
        "hijri": data.today.hijri,
    }
