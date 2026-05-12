"""Home Assistant custom integration for Xplora kids watches."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import XploraApi
from .const import (
    CONF_COUNTRY_CODE,
    CONF_PHONE_NUMBER,
    CONF_TIME_ZONE,
    CONF_USER_LANGUAGE,
    DATA_API,
    DATA_COORDINATOR,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import XploraKidsDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Xplora Kids from a config entry."""
    session = async_get_clientsession(hass)
    api = XploraApi(
        session,
        email=entry.data.get(CONF_EMAIL),
        country_code=entry.data.get(CONF_COUNTRY_CODE),
        phone_number=entry.data.get(CONF_PHONE_NUMBER),
        password=entry.data[CONF_PASSWORD],
        user_language=entry.data[CONF_USER_LANGUAGE],
        time_zone=entry.data[CONF_TIME_ZONE],
    )
    coordinator = XploraKidsDataUpdateCoordinator(hass, entry, api)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_API: api,
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Xplora Kids config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
