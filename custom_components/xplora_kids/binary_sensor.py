"""Binary sensor platform for Xplora Kids."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_LAST_SEEN,
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
    """Set up Xplora Kids binary sensors."""
    coordinator: XploraKidsDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities: list[BinarySensorEntity] = []
    for watch in coordinator.api.watches:
        entities.extend(
            [
                XploraChargingBinarySensor(coordinator, watch),
                XploraSafeZoneBinarySensor(coordinator, watch),
                XploraAdjustedLocationBinarySensor(coordinator, watch),
            ]
        )
    async_add_entities(entities)


class XploraChargingBinarySensor(XploraKidsEntity, BinarySensorEntity):
    """Charging status for a watch."""

    _attr_icon = "mdi:battery-charging"
    _attr_translation_key = "charging"

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the charging binary sensor."""
        super().__init__(coordinator, watch, "charging")

    @property
    def is_on(self) -> bool | None:
        """Return whether the watch is charging."""
        return self.snapshot.charging if self.snapshot else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra charging attributes."""
        attributes = self._base_attributes()
        if self.snapshot is not None:
            attributes[ATTR_LAST_SEEN] = self.snapshot.last_seen
        return attributes


class XploraSafeZoneBinarySensor(XploraKidsEntity, BinarySensorEntity):
    """Safe-zone status for a watch."""

    _attr_icon = "mdi:shield-home"
    _attr_translation_key = "in_safe_zone"

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the safe-zone binary sensor."""
        super().__init__(coordinator, watch, "in_safe_zone")

    @property
    def is_on(self) -> bool | None:
        """Return whether the watch is inside a safe zone."""
        return self.snapshot.is_in_safe_zone if self.snapshot else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra safe-zone attributes."""
        attributes = self._base_attributes()
        if self.snapshot is not None:
            attributes[ATTR_SAFE_ZONE_LABEL] = self.snapshot.safe_zone_label
            attributes[ATTR_LAST_SEEN] = self.snapshot.last_seen
        return attributes


class XploraAdjustedLocationBinarySensor(XploraKidsEntity, BinarySensorEntity):
    """Adjusted-location status for a watch."""

    _attr_icon = "mdi:map-marker-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "adjusted_location"

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the adjusted-location binary sensor."""
        super().__init__(coordinator, watch, "adjusted_location")

    @property
    def is_on(self) -> bool | None:
        """Return whether Xplora marks the location as adjusted."""
        return self.snapshot.is_adjusted if self.snapshot else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra adjusted-location attributes."""
        attributes = self._base_attributes()
        if self.snapshot is not None:
            attributes[ATTR_LAST_SEEN] = self.snapshot.last_seen
        return attributes
