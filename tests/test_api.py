"""Tests for the Xplora API wrapper."""

from __future__ import annotations

import asyncio
import sys
from time import time
import types
import unittest

from support import load_module


class StubXploraApi:
    """Mixin for API tests that avoids network login."""

    async def async_login(self, *, force: bool = False) -> None:
        """Skip login in tests."""


class ApiTest(unittest.TestCase):
    """Test the Xplora API wrapper."""

    def test_parse_watches(self) -> None:
        """Parse watches from the sign-in payload."""
        api_module = _load_api("xplora_kids_api_parse")

        watches = api_module._parse_watches(
            {
                "children": [
                    {
                        "ward": {
                            "id": "watch-1",
                            "userId": "user-1",
                            "name": "Child",
                            "phoneNumber": "491234",
                        }
                    },
                    {"id": "fallback-123456", "ward": {}},
                ]
            }
        )

        assert watches[0] == api_module.XploraWatch(
            id="watch-1",
            name="Child",
            phone_number="491234",
            user_id="user-1",
        )
        assert watches[1].id == "fallback-123456"
        assert watches[1].name == "Watch 123456"

    def test_snapshot_parses_location_payload(self) -> None:
        """Parse watch location payloads into typed snapshots."""
        api_module = _load_api("xplora_kids_api_snapshot")

        class FakeApi(StubXploraApi, api_module.XploraApi):
            async def _graphql(self, query, variables, operation_name, *, open_authorization=False):
                return {
                    "data": {
                        "watchLastLocate": {
                            "tm": 1_700_000_000_000,
                            "lat": "52.5",
                            "lng": "13.4",
                            "rad": "15",
                            "addr": "Example Street",
                            "battery": "88",
                            "isCharging": "true",
                            "isAdjusted": False,
                            "locateType": "gps",
                            "step": "1234",
                            "distance": "55",
                            "isInSafeZone": 1,
                            "safeZoneLabel": "Home",
                            "batteryTm": 1_700_000_100,
                        }
                    }
                }

        api = FakeApi(None, password="", user_language="en-GB", time_zone="UTC")
        watch = api_module.XploraWatch(id="watch-1", name="Watch")

        snapshot = asyncio.run(api.async_get_watch_snapshot(watch))

        assert snapshot.latitude == 52.5
        assert snapshot.longitude == 13.4
        assert snapshot.accuracy == 15
        assert snapshot.battery == 88
        assert snapshot.charging is True
        assert snapshot.steps == 1234
        assert snapshot.distance == 55
        assert snapshot.is_in_safe_zone is True
        assert snapshot.last_seen == "2023-11-14T22:13:20+00:00"
        assert snapshot.battery_updated_at == "2023-11-14T22:15:00+00:00"

    def test_update_watches_keeps_successful_watches_when_one_fails(self) -> None:
        """A single failed watch should not fail the whole coordinator update."""
        api_module = _load_api("xplora_kids_api_partial")

        watch_ok = api_module.XploraWatch(id="ok", name="OK")
        watch_failed = api_module.XploraWatch(id="failed", name="Failed")
        snapshot_ok = _snapshot(api_module, watch_ok, battery=75)

        class FakeApi(StubXploraApi, api_module.XploraApi):
            async def async_get_watch_snapshot(self, watch):
                if watch.id == "failed":
                    raise api_module.XploraApiError("temporary failure")
                return snapshot_ok

        api = FakeApi(None, password="", user_language="en-GB", time_zone="UTC")
        api.watches = [watch_ok, watch_failed]

        snapshots = asyncio.run(api.async_update_watches())

        assert snapshots == {"ok": snapshot_ok}
        assert api.watch_errors == {"failed": "temporary failure"}

    def test_update_watches_uses_cached_snapshot_for_failed_watch(self) -> None:
        """Cached snapshots are kept when a later watch update fails."""
        api_module = _load_api("xplora_kids_api_cached")

        watch = api_module.XploraWatch(id="watch", name="Watch")
        snapshot = _snapshot(api_module, watch, battery=90)

        class FakeApi(StubXploraApi, api_module.XploraApi):
            fail = False

            async def async_get_watch_snapshot(self, watch):
                if self.fail:
                    raise api_module.XploraApiError("temporary failure")
                return snapshot

        api = FakeApi(None, password="", user_language="en-GB", time_zone="UTC")
        api.watches = [watch]

        assert asyncio.run(api.async_update_watches()) == {"watch": snapshot}
        api.fail = True

        assert asyncio.run(api.async_update_watches()) == {"watch": snapshot}
        assert api.watch_errors == {"watch": "temporary failure"}

    def test_update_watches_reraises_authentication_errors(self) -> None:
        """Authentication failures should still trigger Home Assistant reauth."""
        api_module = _load_api("xplora_kids_api_auth")

        watch = api_module.XploraWatch(id="watch", name="Watch")

        class FakeApi(StubXploraApi, api_module.XploraApi):
            async def async_get_watch_snapshot(self, watch):
                raise api_module.XploraAuthenticationError("invalid session")

        api = FakeApi(None, password="", user_language="en-GB", time_zone="UTC")
        api.watches = [watch]

        with self.assertRaises(api_module.XploraAuthenticationError):
            asyncio.run(api.async_update_watches())

    def test_location_request_cooldown(self) -> None:
        """Location requests are throttled before reaching the API."""
        api_module = _load_api("xplora_kids_api_throttle")
        api = api_module.XploraApi(
            None,
            password="",
            user_language="en-GB",
            time_zone="UTC",
        )
        api._last_location_request_at["watch"] = time()

        with self.assertRaises(api_module.XploraLocationRequestThrottled) as err:
            asyncio.run(api.async_request_watch_location("watch", cooldown=60))

        assert 0 < err.exception.retry_after <= 60


def _load_api(name: str):
    """Load the API module with a minimal aiohttp stub for local unit tests."""
    aiohttp = types.ModuleType("aiohttp")

    class ClientError(Exception):
        """Stub aiohttp client error."""

    class ClientTimeout:
        """Stub aiohttp timeout object."""

        def __init__(self, *, total: int) -> None:
            self.total = total

    aiohttp.ClientError = ClientError
    aiohttp.ClientTimeout = ClientTimeout
    sys.modules["aiohttp"] = aiohttp
    return load_module(name, "custom_components/xplora_kids/api.py")


def _snapshot(api_module, watch, *, battery: int):
    """Return a minimal test snapshot."""
    return api_module.XploraWatchSnapshot(
        watch=watch,
        latitude=None,
        longitude=None,
        accuracy=None,
        battery=battery,
        charging=False,
        last_seen=None,
        battery_updated_at=None,
        locate_type=None,
        address=None,
        poi=None,
        city=None,
        province=None,
        country=None,
        country_abbr=None,
        is_in_safe_zone=None,
        safe_zone_label=None,
        is_adjusted=None,
        steps=None,
        distance=None,
        raw={},
    )


if __name__ == "__main__":
    unittest.main()
