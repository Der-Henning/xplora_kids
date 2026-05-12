"""Data coordinator for the Xplora Kids integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import XploraApi, XploraApiError, XploraAuthenticationError, XploraWatchSnapshot
from .const import (
    CONF_LOCATION_REQUEST_COOLDOWN,
    CONF_REQUEST_LOCATION,
    CONF_SCAN_INTERVAL,
    DEFAULT_LOCATION_REQUEST_COOLDOWN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class XploraKidsDataUpdateCoordinator(DataUpdateCoordinator[dict[str, XploraWatchSnapshot]]):
    """Fetch Xplora watch location and battery data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: XploraApi) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.api = api
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, XploraWatchSnapshot]:
        """Fetch data from Xplora."""
        try:
            return await self.api.async_update_watches(
                request_location=self.entry.options.get(CONF_REQUEST_LOCATION, False),
                location_request_cooldown=self.entry.options.get(
                    CONF_LOCATION_REQUEST_COOLDOWN,
                    DEFAULT_LOCATION_REQUEST_COOLDOWN,
                ),
            )
        except XploraAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except XploraApiError as err:
            raise UpdateFailed(str(err)) from err
