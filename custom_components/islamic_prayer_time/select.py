"""Select entities: calculation method and Asr school, changeable at runtime."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CALC_METHODS,
    CONF_CALC_METHOD,
    CONF_LAT_ADJ_METHOD,
    CONF_SCHOOL,
    DEFAULT_CALC_METHOD,
    DEFAULT_LAT_ADJ_METHOD,
    DEFAULT_SCHOOL,
    LAT_ADJ_METHODS,
    SCHOOLS,
)
from .coordinator import PrayerConfigEntry, PrayerTimeCoordinator
from .entity import PrayerTimeEntity

_SELECTS: tuple[tuple[str, str, list[str], str, str, bool], ...] = (
    ("calculation_method", CONF_CALC_METHOD, CALC_METHODS, DEFAULT_CALC_METHOD, "mdi:calculator-variant-outline", True),
    ("school", CONF_SCHOOL, SCHOOLS, DEFAULT_SCHOOL, "mdi:book-open-variant", True),
    ("latitude_adjustment_method", CONF_LAT_ADJ_METHOD, LAT_ADJ_METHODS, DEFAULT_LAT_ADJ_METHOD, "mdi:earth", False),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PrayerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator = entry.runtime_data
    async_add_entities(OptionSelect(coordinator, *spec) for spec in _SELECTS)


class OptionSelect(PrayerTimeEntity, SelectEntity):
    """Select bound to one config-entry option."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: PrayerTimeCoordinator,
        key: str,
        option_key: str,
        options: list[str],
        default: str,
        icon: str,
        enabled: bool,
    ) -> None:
        super().__init__(coordinator, key)
        self._option_key = option_key
        self._default = default
        self._attr_options = options
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled

    @property
    def current_option(self) -> str:
        return self.coordinator.config_entry.options.get(self._option_key, self._default)

    async def async_select_option(self, option: str) -> None:
        entry = self.coordinator.config_entry
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, self._option_key: option}
        )
