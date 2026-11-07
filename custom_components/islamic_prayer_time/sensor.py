"""Sensors: prayer times, current / next prayer and Hijri date."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EXTRA_TIMES, PRAYER_ICONS, PRAYERS
from .coordinator import PrayerConfigEntry, PrayerData, PrayerTimeCoordinator
from .entity import PrayerTimeEntity


@dataclass(frozen=True, kw_only=True)
class PrayerSensorDescription(SensorEntityDescription):
    """Sensor description with value / attribute callbacks."""

    value_fn: Callable[[PrayerData], Any]
    attrs_fn: Callable[[PrayerData], dict[str, Any]] | None = None


def _time_attrs(key: str) -> Callable[[PrayerData], dict[str, Any]]:
    def _attrs(data: PrayerData) -> dict[str, Any]:
        return {
            "calculated": data.today.calculated[key].isoformat(),
            "offset_minutes": data.settings.offsets.get(key, 0),
            "tomorrow": data.tomorrow.adjusted[key].isoformat(),
        }

    return _attrs


def _time_sensor(key: str, enabled: bool) -> PrayerSensorDescription:
    return PrayerSensorDescription(
        key=key,
        translation_key=key,
        icon=PRAYER_ICONS[key],
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=enabled,
        value_fn=lambda d, k=key: d.today.adjusted[k],
        attrs_fn=_time_attrs(key),
    )


def _schedule(data: PrayerData) -> list[dict[str, Any]]:
    return [
        {"prayer": p, "time": data.today.adjusted[p].isoformat()} for p in PRAYERS
    ]


SENSORS: tuple[PrayerSensorDescription, ...] = (
    *(_time_sensor(p, True) for p in PRAYERS),
    *(_time_sensor(p, p == "midnight") for p in EXTRA_TIMES),
    PrayerSensorDescription(
        key="current_prayer",
        translation_key="current_prayer",
        icon="mdi:clock-star-four-points-outline",
        device_class=SensorDeviceClass.ENUM,
        options=PRAYERS,
        value_fn=lambda d: d.current,
        attrs_fn=lambda d: {
            "started": d.current_start.isoformat(),
            "ends": d.next_start.isoformat(),
        },
    ),
    PrayerSensorDescription(
        key="next_prayer",
        translation_key="next_prayer",
        icon="mdi:mosque",
        device_class=SensorDeviceClass.ENUM,
        options=PRAYERS,
        value_fn=lambda d: d.next,
        attrs_fn=lambda d: {"time": d.next_start.isoformat()},
    ),
    PrayerSensorDescription(
        key="next_prayer_time",
        translation_key="next_prayer_time",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.next_start,
        attrs_fn=lambda d: {"prayer": d.next, "schedule": _schedule(d)},
    ),
    PrayerSensorDescription(
        key="hijri_date",
        translation_key="hijri_date",
        icon="mdi:calendar-star",
        value_fn=lambda d: d.today.hijri["formatted"],
        attrs_fn=lambda d: {
            k: v for k, v in d.today.hijri.items() if k != "formatted"
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PrayerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities(PrayerSensor(coordinator, desc) for desc in SENSORS)


class PrayerSensor(PrayerTimeEntity, SensorEntity):
    """A prayer-time sensor."""

    entity_description: PrayerSensorDescription

    def __init__(
        self, coordinator: PrayerTimeCoordinator, description: PrayerSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> datetime | str | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
