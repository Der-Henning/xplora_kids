"""Sensor platform for Xplora Kids."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BATTERY_UPDATED_AT,
    ATTR_CHARGING,
    ATTR_LAST_SEEN,
    ATTR_STEP_DATE,
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
            ]
        )
    async_add_entities(entities)


class XploraBatterySensor(XploraKidsEntity, SensorEntity):
    """Battery level sensor for a watch."""

    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
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
    """Daily step counter sensor for a watch."""

    _attr_name = "Steps Today"
    _attr_icon = "mdi:shoe-print"
    _attr_native_unit_of_measurement = "steps"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: XploraKidsDataUpdateCoordinator, watch) -> None:
        """Initialize the step sensor."""
        super().__init__(coordinator, watch, "steps_today")

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
                ATTR_STEP_DATE: snapshot.step_date,
                ATTR_LAST_SEEN: snapshot.last_seen,
            }
        )
        return attributes
