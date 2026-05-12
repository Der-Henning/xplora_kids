"""Shared entity helpers for Xplora Kids."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import XploraWatch, XploraWatchSnapshot
from .const import CONF_WATCH_MACS, DOMAIN, MANUFACTURER
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
    def available(self) -> bool:
        """Return if the watch entity has a current usable snapshot."""
        return (
            super().available
            and self.snapshot is not None
            and self.watch.id not in self.coordinator.api.watch_errors
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this watch."""
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self.watch.id)},
            manufacturer=MANUFACTURER,
            name=self.watch.name,
        )
        watch_macs = self.coordinator.entry.options.get(CONF_WATCH_MACS, {})
        if mac_address := watch_macs.get(self.watch.id):
            device_info["connections"] = {(CONNECTION_NETWORK_MAC, mac_address)}
        return device_info

    def _base_attributes(self) -> dict[str, str]:
        """Return common entity attributes."""
        return {"watch_id": self.watch.id}
