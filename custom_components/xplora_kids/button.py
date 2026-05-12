"""Button platform for Xplora Kids."""

from __future__ import annotations

import asyncio

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import XploraApiError, XploraAuthenticationError
from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import XploraKidsDataUpdateCoordinator
from .entity import XploraKidsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Xplora Kids buttons."""
    coordinator: XploraKidsDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        XploraRequestLocationButton(coordinator, watch)
        for watch in coordinator.api.watches
    )


class XploraRequestLocationButton(XploraKidsEntity, ButtonEntity):
    """Button to ask a watch for a fresh location."""

    _attr_name = "Request Location"
    _attr_icon = "mdi:crosshairs-gps"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the request-location button."""
        super().__init__(coordinator, watch, "request_location")

    async def async_press(self) -> None:
        """Request a fresh watch location and refresh Home Assistant data."""
        try:
            requested = await self.coordinator.api.async_request_watch_location(self.watch.id)
        except XploraAuthenticationError as err:
            raise HomeAssistantError("Xplora authentication failed while requesting location.") from err
        except XploraApiError as err:
            raise HomeAssistantError(f"Could not request Xplora location: {err}") from err

        if not requested:
            raise HomeAssistantError("Xplora did not accept the location request.")

        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()
