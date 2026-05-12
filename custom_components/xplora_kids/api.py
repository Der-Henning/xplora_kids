"""Minimal async client for the unofficial Xplora GraphQL API."""

from __future__ import annotations

from collections.abc import Mapping
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import logging
import math
from time import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

API_KEY = "fc45d50304511edbf67a12b93c413b6a"
API_SECRET = "1e9b6fe0327711ed959359c157878dcb"
ENDPOINT = "https://api.myxplora.com/api"
DEFAULT_TIMEOUT = 60
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.3"
)
FAILED_LOCATION_REQUEST_BACKOFF = 300

SIGN_IN_MUTATION = """
mutation signInWithEmailOrPhone(
  $countryPhoneNumber: String,
  $phoneNumber: String,
  $password: String!,
  $emailAddress: String,
  $client: ClientType!,
  $userLang: String!,
  $timeZone: String!
) {
  signInWithEmailOrPhone(
    countryPhoneNumber: $countryPhoneNumber,
    phoneNumber: $phoneNumber,
    password: $password,
    emailAddress: $emailAddress,
    client: $client,
    userLang: $userLang,
    timeZone: $timeZone
  ) {
    id
    token
    refreshToken
    issueDate
    expireDate
    valid
    user {
      id
      userId
      name
      nickname
      emailAddress
      countryPhoneCode
      phoneNumber
      children {
        id
        ward {
          id
          userId
          name
          nickname
          countryPhoneCode
          phoneNumber
        }
      }
    }
    w360 {
      token
      secret
      qid
    }
  }
}
"""

ASK_WATCH_LOCATE_QUERY = """
query AskWatchLocate($uid: String!) {
  askWatchLocate(uid: $uid)
}
"""

WATCH_LAST_LOCATE_QUERY = """
query WatchLastLocate($uid: String!) {
  watchLastLocate(uid: $uid) {
    tm
    lat
    lng
    rad
    country
    countryAbbr
    province
    city
    addr
    poi
    battery
    isCharging
    isAdjusted
    locateType
    step
    distance
    isInSafeZone
    safeZoneLabel
    batteryTm
  }
}
"""


@dataclass(slots=True, frozen=True)
class XploraWatch:
    """A watch attached to the signed-in parent account."""

    id: str
    name: str
    phone_number: str | None = None
    user_id: str | None = None


@dataclass(slots=True, frozen=True)
class XploraWatchSnapshot:
    """Latest watch telemetry exposed to Home Assistant."""

    watch: XploraWatch
    latitude: float | None
    longitude: float | None
    accuracy: int | None
    battery: int | None
    charging: bool | None
    last_seen: str | None
    battery_updated_at: str | None
    locate_type: str | None
    address: str | None
    poi: str | None
    city: str | None
    province: str | None
    country: str | None
    country_abbr: str | None
    is_in_safe_zone: bool | None
    safe_zone_label: str | None
    is_adjusted: bool | None
    steps: int | None
    distance: int | None
    raw: dict[str, Any]


class XploraApiError(Exception):
    """Base exception for Xplora API failures."""


class XploraAuthenticationError(XploraApiError):
    """Raised when Xplora rejects the configured credentials."""


class XploraLocationRequestThrottled(XploraApiError):
    """Raised when a location refresh request is currently throttled."""

    def __init__(self, retry_after: int) -> None:
        """Initialize the throttled error."""
        self.retry_after = retry_after
        super().__init__(
            f"Location refresh was requested too recently. Try again in {retry_after} seconds."
        )


class XploraApi:
    """Small Xplora GraphQL API wrapper.

    This intentionally implements only the calls needed for location and battery
    state, so the Home Assistant integration is not tied to a large archived
    integration surface.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        password: str,
        user_language: str,
        time_zone: str,
        email: str | None = None,
        country_code: str | None = None,
        phone_number: str | None = None,
    ) -> None:
        self._session = session
        self._password = password
        self._user_language = user_language
        self._time_zone = time_zone
        self._email = email
        self._country_code = country_code
        self._phone_number = phone_number

        self._api_key = API_KEY
        self._api_secret = API_SECRET
        self._access_token: str | None = None
        self._token_expires_at: float | None = None
        self._issue_token: dict[str, Any] | None = None

        self.account_id: str | None = None
        self.account_name: str | None = None
        self.watches: list[XploraWatch] = []
        self._last_snapshots: dict[str, XploraWatchSnapshot] = {}
        self._watch_errors: dict[str, str] = {}
        self._last_location_request_at: dict[str, float] = {}
        self._location_request_backoff_until: dict[str, float] = {}

    @property
    def watch_by_id(self) -> dict[str, XploraWatch]:
        """Return watches keyed by Xplora user id."""
        return {watch.id: watch for watch in self.watches}

    @property
    def watch_errors(self) -> Mapping[str, str]:
        """Return update errors keyed by watch id."""
        return self._watch_errors.copy()

    @property
    def location_request_cooldowns(self) -> Mapping[str, int]:
        """Return remaining location request cooldowns keyed by watch id."""
        now = time()
        cooldowns: dict[str, int] = {}
        for watch_id, blocked_until in self._location_request_backoff_until.items():
            if blocked_until > now:
                cooldowns[watch_id] = math.ceil(blocked_until - now)
        return cooldowns

    async def async_login(self, *, force: bool = False) -> None:
        """Log in if needed and cache the account watch list."""
        if not force and self._access_token and not self._token_has_expired():
            return

        variables = {
            "countryPhoneNumber": self._country_code,
            "phoneNumber": self._phone_number,
            "password": hashlib.md5(self._password.encode("utf-8")).hexdigest(),
            "emailAddress": self._email,
            "client": "APP",
            "userLang": self._user_language,
            "timeZone": self._time_zone,
        }

        result = await self._graphql(
            SIGN_IN_MUTATION,
            variables,
            "signInWithEmailOrPhone",
            open_authorization=True,
        )
        sign_in = result.get("data", {}).get("signInWithEmailOrPhone")
        if not sign_in:
            raise XploraAuthenticationError("Xplora sign-in returned no session.")

        self._issue_token = sign_in
        self._access_token = sign_in.get("token")
        self._token_expires_at = _as_epoch(sign_in.get("expireDate"))

        w360 = sign_in.get("w360") or {}
        if w360.get("token") and w360.get("secret"):
            self._api_key = w360["token"]
            self._api_secret = w360["secret"]

        user = sign_in.get("user") or {}
        self.account_id = _as_str(user.get("id") or user.get("userId"))
        self.account_name = _as_str(user.get("name") or user.get("nickname"))
        self.watches = _parse_watches(user)

    async def async_validate_credentials(self) -> list[XploraWatch]:
        """Validate credentials and return discovered watches."""
        await self.async_login(force=True)
        return self.watches

    async def async_update_watches(
        self,
        *,
        request_location: bool = False,
        location_request_cooldown: int = 0,
    ) -> dict[str, XploraWatchSnapshot]:
        """Fetch latest telemetry for all watches on the account."""
        await self.async_login()

        snapshots: dict[str, XploraWatchSnapshot] = {}
        errors: dict[str, XploraApiError] = {}
        for watch in self.watches:
            if request_location:
                try:
                    await self.async_request_watch_location(
                        watch.id,
                        cooldown=location_request_cooldown,
                    )
                    await asyncio.sleep(1)
                except XploraLocationRequestThrottled as err:
                    _LOGGER.debug(
                        "Skipping live location request for %s for another %s seconds",
                        watch.id,
                        err.retry_after,
                    )
                except XploraApiError as err:
                    _LOGGER.debug("Could not request live location for %s: %s", watch.id, err)

            try:
                snapshot = await self.async_get_watch_snapshot(watch)
            except XploraAuthenticationError:
                raise
            except XploraApiError as err:
                errors[watch.id] = err
                self._watch_errors[watch.id] = str(err)
                if watch.id in self._last_snapshots:
                    snapshots[watch.id] = self._last_snapshots[watch.id]
                _LOGGER.debug("Could not update Xplora watch %s: %s", watch.id, err)
                continue

            snapshots[watch.id] = snapshot
            self._last_snapshots[watch.id] = snapshot
            self._watch_errors.pop(watch.id, None)

        if not snapshots and errors:
            message = "; ".join(f"{watch_id}: {error}" for watch_id, error in errors.items())
            raise XploraApiError(f"Could not update any Xplora watch: {message}")
        return snapshots

    async def async_request_watch_location(self, watch_id: str, *, cooldown: int = 0) -> bool:
        """Ask a watch to refresh its own location."""
        self._raise_if_location_request_blocked(watch_id, cooldown)
        try:
            result = await self._graphql(
                ASK_WATCH_LOCATE_QUERY,
                {"uid": watch_id},
                "AskWatchLocate",
            )
        except XploraAuthenticationError:
            raise
        except XploraApiError:
            self._location_request_backoff_until[watch_id] = time() + FAILED_LOCATION_REQUEST_BACKOFF
            raise

        requested = bool(result.get("data", {}).get("askWatchLocate"))
        if requested:
            self._last_location_request_at[watch_id] = time()
            self._location_request_backoff_until.pop(watch_id, None)
        return requested

    async def async_get_watch_snapshot(self, watch: XploraWatch) -> XploraWatchSnapshot:
        """Fetch the last known location payload for a watch."""
        result = await self._graphql(
            WATCH_LAST_LOCATE_QUERY,
            {"uid": watch.id},
            "WatchLastLocate",
        )
        location = result.get("data", {}).get("watchLastLocate") or {}

        return XploraWatchSnapshot(
            watch=watch,
            latitude=_as_float(location.get("lat")),
            longitude=_as_float(location.get("lng")),
            accuracy=_as_int(location.get("rad")),
            battery=_as_int(location.get("battery")),
            charging=_as_bool(location.get("isCharging")),
            last_seen=_as_datetime_string(location.get("tm")),
            battery_updated_at=_as_datetime_string(location.get("batteryTm")),
            locate_type=_as_str(location.get("locateType")),
            address=_first_text(
                location.get("addr"),
                location.get("poi"),
                location.get("city"),
                location.get("province"),
                location.get("country"),
            ),
            poi=_as_str(location.get("poi")),
            city=_as_str(location.get("city")),
            province=_as_str(location.get("province")),
            country=_as_str(location.get("country")),
            country_abbr=_as_str(location.get("countryAbbr")),
            is_in_safe_zone=_as_bool(location.get("isInSafeZone")),
            safe_zone_label=_as_str(location.get("safeZoneLabel")),
            is_adjusted=_as_bool(location.get("isAdjusted")),
            steps=_as_int(location.get("step")),
            distance=_as_int(location.get("distance")),
            raw=location,
        )

    async def _graphql(
        self,
        query: str,
        variables: Mapping[str, Any],
        operation_name: str,
        *,
        open_authorization: bool = False,
    ) -> dict[str, Any]:
        """Execute a GraphQL request."""
        headers = self._headers(open_authorization=open_authorization)
        payload = {
            "query": query,
            "variables": dict(variables),
            "operationName": operation_name,
        }

        try:
            async with self._session.post(
                ENDPOINT,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                response_text = await response.text()
                if response.status in (401, 403):
                    raise XploraAuthenticationError(
                        f"Xplora rejected the request with HTTP {response.status}."
                    )
                if response.status >= 400:
                    raise XploraApiError(
                        f"Xplora returned HTTP {response.status}: {response_text[:200]}"
                    )
                data: dict[str, Any] = await response.json()
        except TimeoutError as err:
            raise XploraApiError("Timed out while contacting Xplora.") from err
        except aiohttp.ClientError as err:
            raise XploraApiError(f"Could not contact Xplora: {err}") from err

        errors = data.get("errors") or []
        if errors:
            message = _graphql_error_message(errors)
            lower_message = message.lower()
            if any(
                token in lower_message
                for token in ("auth", "login", "password", "credential")
            ):
                raise XploraAuthenticationError(message)
            raise XploraApiError(message)

        return data

    def _headers(self, *, open_authorization: bool = False) -> dict[str, str]:
        """Build Xplora request headers."""
        if open_authorization or not self._issue_token:
            authorization = f"Open {API_KEY}:{API_SECRET}"
        elif self._issue_token.get("w360"):
            w360 = self._issue_token["w360"]
            authorization = f"Bearer {w360.get('token', self._api_key)}:{w360.get('secret', self._api_secret)}"
        else:
            authorization = f"Bearer {self._access_token}:{self._api_secret}"

        return {
            "H-Date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "H-Tid": str(math.floor(time())),
            "Content-Type": "application/json; charset=UTF-8",
            "H-BackDoor-Authorization": authorization,
            "User-Agent": DEFAULT_USER_AGENT,
        }

    def _token_has_expired(self) -> bool:
        """Return true if the cached token is missing or close to expiry."""
        if self._token_expires_at is None:
            return False
        return self._token_expires_at <= time() + 60

    def _raise_if_location_request_blocked(self, watch_id: str, cooldown: int) -> None:
        """Raise if a location request should be throttled."""
        now = time()
        blocked_until = self._location_request_backoff_until.get(watch_id, 0)

        if cooldown > 0 and watch_id in self._last_location_request_at:
            blocked_until = max(
                blocked_until,
                self._last_location_request_at[watch_id] + cooldown,
            )

        if blocked_until > now:
            raise XploraLocationRequestThrottled(math.ceil(blocked_until - now))


def _parse_watches(user: Mapping[str, Any]) -> list[XploraWatch]:
    """Parse child/ward records from the login response."""
    watches: list[XploraWatch] = []
    for child in user.get("children") or []:
        ward = child.get("ward") or {}
        watch_id = _as_str(ward.get("id") or child.get("id"))
        if not watch_id:
            continue
        phone_number = _as_str(ward.get("phoneNumber"))
        name = _first_text(
            ward.get("name"),
            ward.get("nickname"),
            phone_number,
            f"Watch {watch_id[-6:]}",
        )
        watches.append(
            XploraWatch(
                id=watch_id,
                name=name or f"Watch {watch_id[-6:]}",
                phone_number=phone_number,
                user_id=_as_str(ward.get("userId")),
            )
        )
    return watches


def _graphql_error_message(errors: list[Mapping[str, Any]]) -> str:
    """Flatten GraphQL errors into a readable message."""
    messages = [_as_str(error.get("message")) for error in errors]
    return "; ".join(message for message in messages if message) or "Unknown Xplora API error."


def _as_bool(value: Any) -> bool | None:
    """Convert API booleans while preserving missing values."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_datetime_string(value: Any) -> str | None:
    """Convert epoch seconds/milliseconds into an ISO timestamp."""
    epoch = _as_epoch(value)
    if epoch is None:
        return _as_str(value)
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _as_epoch(value: Any) -> float | None:
    """Convert an API timestamp to epoch seconds."""
    number = _as_float(value)
    if number is None or number <= 0:
        return None
    if number > 10_000_000_000:
        number = number / 1000
    return number


def _as_float(value: Any) -> float | None:
    """Convert an API value to float."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    """Convert an API value to int."""
    if value in (None, ""):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _as_str(value: Any) -> str | None:
    """Convert non-empty API values to strings."""
    if value in (None, ""):
        return None
    return str(value)


def _first_text(*values: Any) -> str | None:
    """Return the first non-empty string value."""
    for value in values:
        text = _as_str(value)
        if text:
            return text
    return None
