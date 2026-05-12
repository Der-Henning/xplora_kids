"""Shared entity helpers for Xplora Kids."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import XploraWatch, XploraWatchSnapshot
from .const import DOMAIN, MANUFACTURER
from .coordinator import XploraKidsDataUpdateCoordinator


class XploraKidsEntity(CoordinatorEntity[XploraKidsDataUpdateCoordinator]):
    """Base entity for a single Xplora watch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: XploraKidsDataUpdateCoordinator,
        watch: XploraWatch,
        entity_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.watch = watch
        self._attr_unique_id = f"{watch.id}_{entity_key}"

    @property
    def snapshot(self) -> XploraWatchSnapshot | None:
        """Return the latest snapshot for this watch."""
        return self.coordinator.data.get(self.watch.id) if self.coordinator.data else None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this watch."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.watch.id)},
            manufacturer=MANUFACTURER,
            name=self.watch.name,
        )

    def _base_attributes(self) -> dict[str, str]:
        """Return common entity attributes."""
        return {"watch_id": self.watch.id}
