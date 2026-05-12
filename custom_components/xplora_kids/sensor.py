"""Sensor platform for Xplora Kids."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength
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
    """Set up Xplora Kids sensors."""
    coordinator: XploraKidsDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities: list[SensorEntity] = []
    for watch in coordinator.api.watches:
        entities.extend(
            [
                XploraBatterySensor(coordinator, watch),
                XploraStepSensor(coordinator, watch),
                XploraLocationAccuracySensor(coordinator, watch),
                XploraWatchDistanceSensor(coordinator, watch),
                XploraLocateTypeSensor(coordinator, watch),
                XploraSafeZoneLabelSensor(coordinator, watch),
                XploraLastSeenSensor(coordinator, watch),
            ]
        )
    async_add_entities(entities)


class XploraBatterySensor(XploraKidsEntity, SensorEntity):
    """Battery level sensor for a watch."""

    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, watch, "battery")

    @property
    def native_value(self) -> int | None:
        """Return battery level."""
        return self.snapshot.battery if self.snapshot else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra battery attributes."""
        attributes = self._base_attributes()
        snapshot = self.snapshot
        if snapshot is None:
            return attributes

        attributes.update(
            {
                ATTR_CHARGING: snapshot.charging,
                ATTR_BATTERY_UPDATED_AT: snapshot.battery_updated_at,
                ATTR_LAST_SEEN: snapshot.last_seen,
            }
        )
        return attributes


class XploraStepSensor(XploraKidsEntity, SensorEntity):
    """Step counter sensor from the latest watch location payload."""

    _attr_name = "Steps"
    _attr_icon = "mdi:shoe-print"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "steps"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the step sensor."""
        super().__init__(coordinator, watch, "steps")

    @property
    def native_value(self) -> int | None:
        """Return today's step count."""
        return self.snapshot.steps if self.snapshot else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra step attributes."""
        attributes = self._base_attributes()
        snapshot = self.snapshot
        if snapshot is None:
            return attributes

        attributes.update(
            {
                ATTR_LAST_SEEN: snapshot.last_seen,
                "source": "watchLastLocate.step",
            }
        )
        return attributes


class XploraLocationAccuracySensor(XploraKidsEntity, SensorEntity):
    """Location accuracy sensor for a watch."""

    _attr_name = "Location Accuracy"
    _attr_icon = "mdi:crosshairs-gps"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the location accuracy sensor."""
        super().__init__(coordinator, watch, "location_accuracy")

    @property
    def native_value(self) -> int | None:
        """Return location accuracy in meters."""
        return self.snapshot.accuracy if self.snapshot else None


class XploraWatchDistanceSensor(XploraKidsEntity, SensorEntity):
    """Distance value from the latest watch location payload."""

    _attr_name = "Distance"
    _attr_icon = "mdi:map-marker-distance"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the distance sensor."""
        super().__init__(coordinator, watch, "distance")

    @property
    def native_value(self) -> int | None:
        """Return the distance reported by Xplora."""
        return self.snapshot.distance if self.snapshot else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra distance attributes."""
        attributes = self._base_attributes()
        if self.snapshot is not None:
            attributes[ATTR_LAST_SEEN] = self.snapshot.last_seen
            attributes["source"] = "watchLastLocate.distance"
        return attributes


class XploraLocateTypeSensor(XploraKidsEntity, SensorEntity):
    """Locate type sensor for a watch."""

    _attr_name = "Locate Type"
    _attr_icon = "mdi:map-search"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the locate type sensor."""
        super().__init__(coordinator, watch, "locate_type")

    @property
    def native_value(self) -> str | None:
        """Return locate type."""
        return self.snapshot.locate_type if self.snapshot else None


class XploraSafeZoneLabelSensor(XploraKidsEntity, SensorEntity):
    """Safe zone label sensor for a watch."""

    _attr_name = "Safe Zone"
    _attr_icon = "mdi:shield-home"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the safe zone label sensor."""
        super().__init__(coordinator, watch, "safe_zone")

    @property
    def native_value(self) -> str | None:
        """Return the current safe zone label."""
        if not self.snapshot:
            return None
        return self.snapshot.safe_zone_label or "not_in_safe_zone"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra safe zone attributes."""
        attributes = self._base_attributes()
        snapshot = self.snapshot
        if snapshot is not None:
            attributes.update(
                {
                    ATTR_IS_IN_SAFE_ZONE: snapshot.is_in_safe_zone,
                    ATTR_LAST_SEEN: snapshot.last_seen,
                }
            )
        return attributes


class XploraLastSeenSensor(XploraKidsEntity, SensorEntity):
    """Last seen timestamp sensor for a watch."""

    _attr_name = "Last Seen"
    _attr_icon = "mdi:clock-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the last seen sensor."""
        super().__init__(coordinator, watch, "last_seen")

    @property
    def native_value(self) -> datetime | None:
        """Return last seen timestamp."""
        if not self.snapshot or not self.snapshot.last_seen:
            return None
        try:
            return datetime.fromisoformat(self.snapshot.last_seen)
        except ValueError:
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra last seen attributes."""
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
            }
        )
        return attributes
