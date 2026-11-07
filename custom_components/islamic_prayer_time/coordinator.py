"""Coordinator: computes prayer times and wakes up exactly when they change."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .calculator import CalcSettings, DayTimes, calculate_day, resolve_current_and_next
from .const import (
    ADJUSTABLE_TIMES,
    CONF_CALC_METHOD,
    CONF_ELEVATION,
    CONF_HIJRI_OFFSET,
    CONF_LAT_ADJ_METHOD,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MIDNIGHT_MODE,
    CONF_OFFSET_PREFIX,
    CONF_SCHOOL,
    CONF_USE_HOME_ELEVATION,
    CONF_USE_HOME_LOCATION,
    DEFAULT_CALC_METHOD,
    DEFAULT_HIJRI_OFFSET,
    DEFAULT_LAT_ADJ_METHOD,
    DEFAULT_MIDNIGHT_MODE,
    DEFAULT_SCHOOL,
    DOMAIN,
    EVENT_PRAYER_TIME,
    PRAYERS,
)

_LOGGER = logging.getLogger(__name__)

type PrayerConfigEntry = ConfigEntry[PrayerTimeCoordinator]


@dataclass
class PrayerData:
    """Snapshot handed to entities."""

    settings: CalcSettings
    today: DayTimes
    tomorrow: DayTimes
    current: str
    next: str
    current_start: datetime
    next_start: datetime


def settings_from_entry(hass: HomeAssistant, entry: ConfigEntry) -> CalcSettings:
    """Build calculation settings from the entry options."""
    opts: dict[str, Any] = {**entry.data, **entry.options}

    if opts.get(CONF_USE_HOME_LOCATION, True):
        latitude = hass.config.latitude
        longitude = hass.config.longitude
        elevation = (
            float(hass.config.elevation or 0)
            if opts.get(CONF_USE_HOME_ELEVATION, False)
            else 0.0
        )
    else:
        latitude = float(opts[CONF_LATITUDE])
        longitude = float(opts[CONF_LONGITUDE])
        elevation = float(opts.get(CONF_ELEVATION, 0) or 0)

    return CalcSettings(
        latitude=latitude,
        longitude=longitude,
        elevation=elevation,
        method=opts.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD),
        school=opts.get(CONF_SCHOOL, DEFAULT_SCHOOL),
        lat_adjustment=opts.get(CONF_LAT_ADJ_METHOD, DEFAULT_LAT_ADJ_METHOD),
        midnight_mode=opts.get(CONF_MIDNIGHT_MODE, DEFAULT_MIDNIGHT_MODE),
        offsets={
            key: int(opts.get(f"{CONF_OFFSET_PREFIX}{key}", 0) or 0)
            for key in ADJUSTABLE_TIMES
        },
        hijri_offset=int(opts.get(CONF_HIJRI_OFFSET, DEFAULT_HIJRI_OFFSET) or 0),
    )


class PrayerTimeCoordinator(DataUpdateCoordinator[PrayerData]):
    """Event-driven coordinator – no polling.

    It recalculates at local midnight and wakes up at every prayer time so the
    current / next prayer sensors flip at the exact minute, and fires an
    `islamic_prayer_time_prayer` event for automations (e.g. playing the adhan).
    """

    config_entry: PrayerConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PrayerConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )
        self._unsub_timer: CALLBACK_TYPE | None = None
        self._unsub_core: CALLBACK_TYPE | None = None
        self._pending_prayer: str | None = None

    # ------------------------------------------------------------------ setup
    async def async_setup(self) -> None:  # type: ignore[override]
        """Listen for HA location changes."""

        @callback
        def _core_config_updated(_event: Event) -> None:
            if self.config_entry.options.get(CONF_USE_HOME_LOCATION, True):
                self.hass.async_create_task(self.async_refresh())

        self._unsub_core = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, _core_config_updated
        )

    @callback
    def async_shutdown_listeners(self) -> None:
        """Stop timers and listeners."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        if self._unsub_core:
            self._unsub_core()
            self._unsub_core = None

    # --------------------------------------------------------------- refresh
    async def _async_update_data(self) -> PrayerData:
        settings = settings_from_entry(self.hass, self.config_entry)
        local_now = dt_util.now()
        today_date = local_now.date()
        try:
            today, tomorrow = await self.hass.async_add_executor_job(
                _calc_pair, settings, today_date
            )
        except Exception as err:  # noqa: BLE001 - library raises plain errors
            raise UpdateFailed(f"Prayer time calculation failed: {err}") from err

        now_utc = dt_util.utcnow()
        current, nxt, current_start, next_start = resolve_current_and_next(
            now_utc, today, tomorrow
        )
        data = PrayerData(
            settings=settings,
            today=today,
            tomorrow=tomorrow,
            current=current,
            next=nxt,
            current_start=current_start,
            next_start=next_start,
        )
        self._schedule_next(data, local_now)
        return data

    @callback
    def _schedule_next(self, data: PrayerData, local_now: datetime) -> None:
        """Wake up at the next prayer or at local midnight, whichever is first."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None

        midnight_local = dt_util.start_of_local_day(local_now + timedelta(days=1))
        wake = dt_util.as_utc(midnight_local)
        self._pending_prayer = None
        if data.next_start < wake:
            wake = data.next_start
            self._pending_prayer = data.next

        self._unsub_timer = async_track_point_in_utc_time(
            self.hass, self._handle_wakeup, wake
        )

    async def _handle_wakeup(self, _now: datetime) -> None:
        self._unsub_timer = None
        prayer = self._pending_prayer
        previous = self.data
        await self.async_refresh()
        if prayer and previous is not None:
            self.hass.bus.async_fire(
                EVENT_PRAYER_TIME,
                {
                    "prayer": prayer,
                    "is_prayer": prayer != "sunrise",
                    "time": previous.next_start.isoformat(),
                    "config_entry_id": self.config_entry.entry_id,
                },
            )


def _calc_pair(settings: CalcSettings, today_date: Any) -> tuple[DayTimes, DayTimes]:
    today = calculate_day(settings, today_date)
    tomorrow = calculate_day(settings, today_date + timedelta(days=1))
    # Sanity check: the six dashboard times must exist.
    for prayer in PRAYERS:
        if prayer not in today.adjusted:
            raise ValueError(f"missing {prayer}")
    return today, tomorrow
