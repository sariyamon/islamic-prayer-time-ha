"""Serve and auto-register the bundled Lovelace cards.

The cards ship inside the integration, so users don't need a separate HACS
"plugin" install or a manual dashboard resource: once the integration is
loaded, every dashboard can use the cards immediately.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, FRONTEND_CARDS_FILE, FRONTEND_URL_BASE, VERSION

_LOGGER = logging.getLogger(__name__)
_REGISTERED = f"{DOMAIN}_frontend_registered"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Expose www/ and inject the card bundle into the frontend."""
    if hass.data.get(_REGISTERED) or hass.http is None:
        return

    www = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL_BASE, str(www), cache_headers=False)]
    )
    # Version query string busts browser caches after an update.
    if "frontend" in hass.config.components:
        from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415

        add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/{FRONTEND_CARDS_FILE}?v={VERSION}")
    hass.data[_REGISTERED] = True
    _LOGGER.debug("Registered prayer time cards at %s", FRONTEND_URL_BASE)
