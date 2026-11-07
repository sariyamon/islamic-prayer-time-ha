"""Number entities: per-prayer minute offsets (+/- min) and Hijri day offset.

Adjusting one of these from a dashboard or automation updates the config entry
options, which immediately recalculates every sensor – no reload, no restart.
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ADJUSTABLE_TIMES,
    CONF_HIJRI_OFFSET,
    CONF_OFFSET_PREFIX,
    HIJRI_OFFSET_RANGE,
    OFFSET_RANGE,
    PRAYERS,
)
from .coordinator import PrayerConfigEntry, PrayerTimeCoordinator
from .entity import PrayerTimeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PrayerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [
        OffsetNumber(coordinator, key) for key in ADJUSTABLE_TIMES
    ]
    entities.append(HijriOffsetNumber(coordinator))
    async_add_entities(entities)


class _OptionNumber(PrayerTimeEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _option_key: str

    @property
    def native_value(self) -> float:
        return float(self.coordinator.config_entry.options.get(self._option_key, 0))

    async def async_set_native_value(self, value: float) -> None:
        entry = self.coordinator.config_entry
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, self._option_key: int(value)}
        )


class OffsetNumber(_OptionNumber):
    """Minute offset for one prayer."""

    _attr_icon = "mdi:clock-plus-outline"
    _attr_native_min_value = OFFSET_RANGE[0]
    _attr_native_max_value = OFFSET_RANGE[1]
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator: PrayerTimeCoordinator, prayer: str) -> None:
        super().__init__(coordinator, f"offset_{prayer}")
        self._option_key = f"{CONF_OFFSET_PREFIX}{prayer}"
        self._attr_entity_registry_enabled_default = prayer in PRAYERS


class HijriOffsetNumber(_OptionNumber):
    """Day adjustment for the Hijri date (local moon sighting)."""

    _attr_icon = "mdi:calendar-sync"
    _attr_native_min_value = HIJRI_OFFSET_RANGE[0]
    _attr_native_max_value = HIJRI_OFFSET_RANGE[1]
    _attr_native_unit_of_measurement = UnitOfTime.DAYS

    def __init__(self, coordinator: PrayerTimeCoordinator) -> None:
        super().__init__(coordinator, "hijri_offset")
        self._option_key = CONF_HIJRI_OFFSET
