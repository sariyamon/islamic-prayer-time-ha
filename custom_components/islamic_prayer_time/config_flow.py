"""Config and options flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    ADJUSTABLE_TIMES,
    CALC_METHODS,
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
    DEFAULT_LAT_ADJ_METHOD,
    DEFAULT_MIDNIGHT_MODE,
    DEFAULT_SCHOOL,
    DOMAIN,
    HIJRI_OFFSET_RANGE,
    LAT_ADJ_METHODS,
    MIDNIGHT_MODES,
    OFFSET_RANGE,
)

CORE_DOMAIN = "islamic_prayer_times"
DEFAULT_TITLE = "Prayer Times"


# ---------------------------------------------------------------- selectors
def _select(options: list[str], key: str) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=options, translation_key=key, mode=SelectSelectorMode.DROPDOWN
        )
    )


def _num(lo: float, hi: float, step: float | str, unit: str | None = None) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=lo, max=hi, step=step, unit_of_measurement=unit, mode=NumberSelectorMode.BOX
        )
    )


def _calculation_schema(d: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Required(CONF_CALC_METHOD, default=d.get(CONF_CALC_METHOD, DEFAULT_CALC_METHOD)): _select(CALC_METHODS, CONF_CALC_METHOD),
        vol.Required(CONF_SCHOOL, default=d.get(CONF_SCHOOL, DEFAULT_SCHOOL)): _select(["shafi", "hanafi"], CONF_SCHOOL),
        vol.Required(CONF_LAT_ADJ_METHOD, default=d.get(CONF_LAT_ADJ_METHOD, DEFAULT_LAT_ADJ_METHOD)): _select(LAT_ADJ_METHODS, CONF_LAT_ADJ_METHOD),
        vol.Required(CONF_MIDNIGHT_MODE, default=d.get(CONF_MIDNIGHT_MODE, DEFAULT_MIDNIGHT_MODE)): _select(MIDNIGHT_MODES, CONF_MIDNIGHT_MODE),
    }


def _location_mode_schema(d: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Required(CONF_USE_HOME_LOCATION, default=d.get(CONF_USE_HOME_LOCATION, True)): BooleanSelector(),
        vol.Required(CONF_USE_HOME_ELEVATION, default=d.get(CONF_USE_HOME_ELEVATION, False)): BooleanSelector(),
    }


def _custom_location_schema(hass: HomeAssistant, d: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_LATITUDE, default=d.get(CONF_LATITUDE, hass.config.latitude)): _num(-90, 90, "any", "°"),
            vol.Required(CONF_LONGITUDE, default=d.get(CONF_LONGITUDE, hass.config.longitude)): _num(-180, 180, "any", "°"),
            vol.Required(CONF_ELEVATION, default=d.get(CONF_ELEVATION, hass.config.elevation or 0)): _num(-500, 9000, 1, "m"),
        }
    )


def _offsets_schema(d: dict[str, Any]) -> vol.Schema:
    schema: dict[Any, Any] = {
        vol.Required(f"{CONF_OFFSET_PREFIX}{key}", default=d.get(f"{CONF_OFFSET_PREFIX}{key}", 0)): _num(OFFSET_RANGE[0], OFFSET_RANGE[1], 1, "min")
        for key in ADJUSTABLE_TIMES
    }
    schema[vol.Required(CONF_HIJRI_OFFSET, default=d.get(CONF_HIJRI_OFFSET, 0))] = _num(HIJRI_OFFSET_RANGE[0], HIJRI_OFFSET_RANGE[1], 1, "d")
    return vol.Schema(schema)


def _ints(data: dict[str, Any]) -> dict[str, Any]:
    """Number selectors return floats; offsets are whole minutes / days."""
    return {
        k: int(v) if (k.startswith(CONF_OFFSET_PREFIX) or k == CONF_HIJRI_OFFSET) else v
        for k, v in data.items()
    }


# -------------------------------------------------------------- config flow
class IslamicPrayerTimeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup."""

    VERSION = 1

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}
        self._title = DEFAULT_TITLE

    def _core_defaults(self) -> dict[str, Any]:
        """Re-use the settings of the core integration if it is configured."""
        entries = self.hass.config_entries.async_entries(CORE_DOMAIN)
        if not entries:
            return {}
        opts = entries[0].options
        return {
            key: opts[key]
            for key in (CONF_CALC_METHOD, CONF_SCHOOL, CONF_LAT_ADJ_METHOD, CONF_MIDNIGHT_MODE)
            if key in opts
        }

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._title = user_input.pop(CONF_NAME) or DEFAULT_TITLE
            self._options.update(user_input)
            if user_input[CONF_USE_HOME_LOCATION]:
                return await self.async_step_offsets()
            return await self.async_step_location()

        defaults = self._core_defaults()
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_TITLE): TextSelector(),
                **_calculation_schema(defaults),
                **_location_mode_schema(defaults),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={"core": "found" if defaults else "not found"},
        )

    async def async_step_location(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_offsets()
        return self.async_show_form(
            step_id="location", data_schema=_custom_location_schema(self.hass, self._options)
        )

    async def async_step_offsets(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(_ints(user_input))
            return self.async_create_entry(title=self._title, data={}, options=self._options)
        return self.async_show_form(step_id="offsets", data_schema=_offsets_schema(self._options))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return IslamicPrayerTimeOptionsFlow()


# ------------------------------------------------------------- options flow
class IslamicPrayerTimeOptionsFlow(OptionsFlow):
    """Change method, location or offsets after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init", menu_options=["calculation", "location", "offsets"]
        )

    def _save(self, changes: dict[str, Any]) -> ConfigFlowResult:
        return self.async_create_entry(data={**self.config_entry.options, **changes})

    async def async_step_calculation(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(user_input)
        return self.async_show_form(
            step_id="calculation",
            data_schema=vol.Schema(_calculation_schema(dict(self.config_entry.options))),
        )

    async def async_step_location(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        opts = dict(self.config_entry.options)
        if user_input is not None:
            if user_input[CONF_USE_HOME_LOCATION]:
                return self._save(user_input)
            self._pending = user_input
            return await self.async_step_custom_location()
        return self.async_show_form(
            step_id="location", data_schema=vol.Schema(_location_mode_schema(opts))
        )

    async def async_step_custom_location(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self._save({**getattr(self, "_pending", {}), **user_input})
        return self.async_show_form(
            step_id="custom_location",
            data_schema=_custom_location_schema(self.hass, dict(self.config_entry.options)),
        )

    async def async_step_offsets(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(_ints(user_input))
        return self.async_show_form(
            step_id="offsets", data_schema=_offsets_schema(dict(self.config_entry.options))
        )



