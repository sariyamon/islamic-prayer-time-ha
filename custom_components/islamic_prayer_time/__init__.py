"""Islamic Prayer Time for Home Assistant.

Accurate, offline prayer times with per-prayer minute offsets, selectable
calculation methods, custom location / elevation and a set of bundled
Lovelace cards that are registered automatically.
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import PrayerConfigEntry, PrayerTimeCoordinator
from .frontend import async_register_frontend

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.NUMBER, Platform.SELECT]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Register the bundled Lovelace cards once, at startup."""
    await async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PrayerConfigEntry) -> bool:
    """Set up a prayer-time location from a config entry."""
    coordinator = PrayerTimeCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(coordinator.async_shutdown_listeners)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PrayerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: PrayerConfigEntry) -> None:
    """Options changed (options flow, number or select entity): recalculate.

    No reload needed – entities keep their state and simply receive new data.
    """
    await entry.runtime_data.async_refresh()
