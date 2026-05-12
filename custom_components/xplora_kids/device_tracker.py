"""Device tracker platform for Xplora Kids."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ADDRESS,
    ATTR_BATTERY_UPDATED_AT,
    ATTR_CITY,
    ATTR_CHARGING,
    ATTR_COUNTRY,
    ATTR_COUNTRY_ABBR,
    ATTR_IS_ADJUSTED,
    ATTR_IS_IN_SAFE_ZONE,
    ATTR_LAST_SEEN,
    ATTR_LOCATE_TYPE,
    ATTR_POI,
    ATTR_PROVINCE,
    ATTR_SAFE_ZONE_LABEL,
    DATA_COORDINATOR,
    DOMAIN,
)
from .coordinator import XploraKidsDataUpdateCoordinator
from .entity import XploraKidsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Xplora Kids device trackers."""
    coordinator: XploraKidsDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        XploraWatchTracker(coordinator, watch)
        for watch in coordinator.api.watches
    )


class XploraWatchTracker(XploraKidsEntity, TrackerEntity):
    """Tracker entity for a watch."""

    _attr_name = None
    _attr_icon = "mdi:watch"

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, watch, "tracker")

    @property
    def latitude(self) -> float | None:
        """Return latitude."""
        return self.snapshot.latitude if self.snapshot else None

    @property
    def longitude(self) -> float | None:
        """Return longitude."""
        return self.snapshot.longitude if self.snapshot else None

    @property
    def location_accuracy(self) -> int | None:
        """Return location accuracy in meters."""
        return self.snapshot.accuracy if self.snapshot else None

    @property
    def battery_level(self) -> int | None:
        """Return battery level."""
        return self.snapshot.battery if self.snapshot else None

    @property
    def source_type(self) -> SourceType:
        """Return tracker source type."""
        return SourceType.GPS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra tracker attributes."""
        attributes = self._base_attributes()
        snapshot = self.snapshot
        if snapshot is None:
            return attributes

        attributes.update(
            {
                ATTR_ADDRESS: snapshot.address,
                ATTR_POI: snapshot.poi,
                ATTR_CITY: snapshot.city,
                ATTR_PROVINCE: snapshot.province,
                ATTR_COUNTRY: snapshot.country,
                ATTR_COUNTRY_ABBR: snapshot.country_abbr,
                ATTR_CHARGING: snapshot.charging,
                ATTR_IS_IN_SAFE_ZONE: snapshot.is_in_safe_zone,
                ATTR_SAFE_ZONE_LABEL: snapshot.safe_zone_label,
                ATTR_IS_ADJUSTED: snapshot.is_adjusted,
                ATTR_LOCATE_TYPE: snapshot.locate_type,
                ATTR_LAST_SEEN: snapshot.last_seen,
                ATTR_BATTERY_UPDATED_AT: snapshot.battery_updated_at,
            }
        )
        return attributes
