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
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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

USER_STEPS_QUERY = """
query UserSteps($uid: String!, $tz: String, $date: Int!) {
  userSteps(uid: $uid, tz: $tz, date: $date) {
    day
    monthSteps {
      key
      step
    }
    daySteps {
      key
      step
    }
    timeSteps {
      key
      step
    }
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
    is_in_safe_zone: bool | None
    steps: int | None
    step_date: str | None
    raw: dict[str, Any]
    raw_steps: dict[str, Any]


class XploraApiError(Exception):
    """Base exception for Xplora API failures."""


class XploraAuthenticationError(XploraApiError):
    """Raised when Xplora rejects the configured credentials."""


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

    @property
    def watch_by_id(self) -> dict[str, XploraWatch]:
        """Return watches keyed by Xplora user id."""
        return {watch.id: watch for watch in self.watches}

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

    async def async_update_watches(self, *, request_location: bool = False) -> dict[str, XploraWatchSnapshot]:
        """Fetch latest telemetry for all watches on the account."""
        await self.async_login()

        snapshots: dict[str, XploraWatchSnapshot] = {}
        for watch in self.watches:
            if request_location:
                try:
                    await self.async_request_watch_location(watch.id)
                    await asyncio.sleep(1)
                except XploraApiError as err:
                    _LOGGER.debug("Could not request live location for %s: %s", watch.id, err)

            snapshots[watch.id] = await self.async_get_watch_snapshot(watch)

        return snapshots

    async def async_request_watch_location(self, watch_id: str) -> bool:
        """Ask a watch to refresh its own location."""
        result = await self._graphql(
            ASK_WATCH_LOCATE_QUERY,
            {"uid": watch_id},
            "AskWatchLocate",
        )
        return bool(result.get("data", {}).get("askWatchLocate"))

    async def async_get_watch_snapshot(self, watch: XploraWatch) -> XploraWatchSnapshot:
        """Fetch the last known location payload for a watch."""
        result = await self._graphql(
            WATCH_LAST_LOCATE_QUERY,
            {"uid": watch.id},
            "WatchLastLocate",
        )
        location = result.get("data", {}).get("watchLastLocate") or {}
        raw_steps: dict[str, Any] = {}
        steps = None
        step_date = None

        try:
            raw_steps, step_date = await self.async_get_watch_steps(watch.id)
            steps = _step_count(raw_steps)
        except XploraApiError as err:
            _LOGGER.debug("Could not fetch step count for %s: %s", watch.id, err)

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
            is_in_safe_zone=_as_bool(location.get("isInSafeZone")),
            steps=steps,
            step_date=step_date,
            raw=location,
            raw_steps=raw_steps,
        )

    async def async_get_watch_steps(self, watch_id: str) -> tuple[dict[str, Any], str]:
        """Fetch today's step data for a watch."""
        date_epoch, step_date = _start_of_day(self._time_zone)
        result = await self._graphql(
            USER_STEPS_QUERY,
            {
                "uid": watch_id,
                "tz": self._time_zone,
                "date": date_epoch,
            },
            "UserSteps",
        )
        return result.get("data", {}).get("userSteps") or {}, step_date

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


def _start_of_day(time_zone: str) -> tuple[int, str]:
    """Return start-of-day epoch and date string for a timezone."""
    try:
        tz = ZoneInfo(time_zone)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp()), start.date().isoformat()


def _step_count(user_steps: Mapping[str, Any]) -> int | None:
    """Extract today's step count from Xplora's userSteps payload."""
    for key in ("day", "step", "steps", "totalStep"):
        value = _as_int(user_steps.get(key))
        if value is not None:
            return value

    for key in ("daySteps", "timeSteps"):
        items = user_steps.get(key)
        if not isinstance(items, list):
            continue
        steps = [
            value
            for item in items
            if isinstance(item, Mapping)
            for value in [_as_int(item.get("step"))]
            if value is not None
        ]
        if steps:
            return sum(steps)

    return None


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
        return int(float(value))
    except (TypeError, ValueError):
        return None


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
