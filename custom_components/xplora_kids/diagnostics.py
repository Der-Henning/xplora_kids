"""Diagnostics support for Xplora Kids."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .api import XploraWatchSnapshot
from .const import (
    CONF_COUNTRY_CODE,
    CONF_PHONE_NUMBER,
    CONF_WATCH_MACS,
    DATA_COORDINATOR,
    DOMAIN,
)
from .coordinator import XploraKidsDataUpdateCoordinator
from .helpers import redacted_hash

TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    "refreshToken",
    "token",
    "w360",
    CONF_COUNTRY_CODE,
    CONF_PHONE_NUMBER,
    CONF_WATCH_MACS,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = _get_coordinator(hass, entry)

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": _coordinator_diagnostics(coordinator),
        "watches": _watches_diagnostics(coordinator),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a single watch device."""
    coordinator = _get_coordinator(hass, entry)
    watch_ids = {
        identifier
        for domain, identifier in device.identifiers
        if domain == DOMAIN
    }

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": _coordinator_diagnostics(coordinator),
        "watches": _watches_diagnostics(coordinator, watch_ids=watch_ids),
    }


def _get_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> XploraKidsDataUpdateCoordinator:
    """Return the data coordinator for a config entry."""
    return hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]


def _coordinator_diagnostics(coordinator: XploraKidsDataUpdateCoordinator) -> dict[str, Any]:
    """Return redacted coordinator diagnostics."""
    return {
        "last_update_success": coordinator.last_update_success,
        "location_request_backoffs": {
            redacted_hash(watch_id): seconds
            for watch_id, seconds in coordinator.api.location_request_cooldowns.items()
        },
        "update_interval_seconds": (
            int(coordinator.update_interval.total_seconds())
            if coordinator.update_interval is not None
            else None
        ),
        "watch_count": len(coordinator.api.watches),
    }


def _watches_diagnostics(
    coordinator: XploraKidsDataUpdateCoordinator,
    *,
    watch_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return redacted diagnostics for watches."""
    diagnostics: list[dict[str, Any]] = []
    watch_errors = getattr(coordinator.api, "watch_errors", {})

    for watch in coordinator.api.watches:
        if watch_ids is not None and watch.id not in watch_ids:
            continue

        snapshot = coordinator.data.get(watch.id) if coordinator.data else None
        diagnostics.append(
            {
                "watch_id_hash": redacted_hash(watch.id),
                "user_id_hash": redacted_hash(watch.user_id),
                "has_phone_number": bool(watch.phone_number),
                "has_update_error": watch.id in watch_errors,
                "snapshot": _snapshot_diagnostics(snapshot),
            }
        )

    return diagnostics


def _snapshot_diagnostics(snapshot: XploraWatchSnapshot | None) -> dict[str, Any]:
    """Return redacted snapshot diagnostics."""
    if snapshot is None:
        return {"available": False}

    return {
        "available": True,
        "has_coordinates": (
            snapshot.latitude is not None
            and snapshot.longitude is not None
        ),
        "has_address": bool(snapshot.address),
        "has_battery": snapshot.battery is not None,
        "has_battery_timestamp": bool(snapshot.battery_updated_at),
        "has_charging_status": snapshot.charging is not None,
        "has_distance": snapshot.distance is not None,
        "has_last_seen": bool(snapshot.last_seen),
        "has_safe_zone": snapshot.is_in_safe_zone is not None,
        "has_steps": snapshot.steps is not None,
        "is_adjusted": snapshot.is_adjusted,
        "locate_type": snapshot.locate_type,
        "raw_keys": sorted(snapshot.raw),
    }
