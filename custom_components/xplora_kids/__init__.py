"""Home Assistant custom integration for Xplora kids watches."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr

from .api import XploraApi
from .const import (
    CONF_COUNTRY_CODE,
    CONF_PHONE_NUMBER,
    CONF_TIME_ZONE,
    CONF_USER_LANGUAGE,
    CONF_WATCH_MACS,
    DATA_API,
    DATA_COORDINATOR,
    DATA_WATCH_MACS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import XploraKidsDataUpdateCoordinator
from .helpers import stale_watch_macs


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
        DATA_WATCH_MACS: dict(entry.options.get(CONF_WATCH_MACS, {})),
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
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    await _async_remove_stale_mac_connections(
        hass,
        entry,
        entry_data.get(DATA_WATCH_MACS, {}),
        entry.options.get(CONF_WATCH_MACS, {}),
    )
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_remove_stale_mac_connections(
    hass: HomeAssistant,
    entry: ConfigEntry,
    previous_watch_macs: dict[str, str],
    current_watch_macs: dict[str, str],
) -> None:
    """Remove MAC connections that are no longer configured for Xplora watches."""
    stale_macs = stale_watch_macs(previous_watch_macs, current_watch_macs)
    if not stale_macs:
        return

    device_registry = dr.async_get(hass)
    for watch_id, mac_address in stale_macs.items():
        device = device_registry.async_get_device(identifiers={(DOMAIN, watch_id)})
        if device is None or entry.entry_id not in device.config_entries:
            continue

        mac_connection = (dr.CONNECTION_NETWORK_MAC, mac_address)
        if mac_connection not in device.connections:
            continue

        device_registry.async_update_device(
            device_id=device.id,
            new_connections=device.connections - {mac_connection},
            new_identifiers=device.identifiers,
        )
