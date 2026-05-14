"""Small helper functions for Xplora Kids."""

from __future__ import annotations

import hashlib
import re
from typing import Any

MAC_PATTERN = re.compile(r"^[0-9a-f]{12}$")


def clean_optional_text(
    value: Any,
    *,
    strip_plus: bool = False,
    strip_spaces: bool = False,
) -> str | None:
    """Clean user-entered optional text."""
    if value is None:
        return None
    text = str(value).strip()
    if strip_plus:
        text = text.removeprefix("+")
    if strip_spaces:
        text = "".join(text.split())
    return text or None


def normalize_mac(value: str) -> str | None:
    """Normalize user-entered MAC addresses to lowercase colon notation."""
    cleaned = value.strip().lower().replace("-", "").replace(":", "").replace(".", "")
    if MAC_PATTERN.fullmatch(cleaned) is None:
        return None
    return ":".join(cleaned[index : index + 2] for index in range(0, 12, 2))


def redacted_hash(value: str | None) -> str | None:
    """Return a stable short hash for diagnostics without exposing raw IDs."""
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def stale_watch_macs(
    previous_watch_macs: dict[str, str],
    current_watch_macs: dict[str, str],
) -> dict[str, str]:
    """Return previously configured MAC addresses no longer used by a watch."""
    return {
        watch_id: mac_address
        for watch_id, mac_address in previous_watch_macs.items()
        if current_watch_macs.get(watch_id) != mac_address
    }
