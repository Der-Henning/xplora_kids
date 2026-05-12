"""Constants for the Xplora Kids integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "xplora_kids"
MANUFACTURER = "Xplora"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]

DATA_API = "api"
DATA_COORDINATOR = "coordinator"

CONF_COUNTRY_CODE = "country_code"
CONF_PHONE_NUMBER = "phone_number"
CONF_USER_LANGUAGE = "user_language"
CONF_TIME_ZONE = "time_zone"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_REQUEST_LOCATION = "request_location"

DEFAULT_SCAN_INTERVAL = 300
DEFAULT_USER_LANGUAGE = "en-GB"
DEFAULT_TIME_ZONE = "UTC"

ATTR_ADDRESS = "address"
ATTR_CITY = "city"
ATTR_BATTERY_UPDATED_AT = "battery_updated_at"
ATTR_CHARGING = "charging"
ATTR_COUNTRY = "country"
ATTR_COUNTRY_ABBR = "country_abbr"
ATTR_IS_ADJUSTED = "is_adjusted"
ATTR_IS_IN_SAFE_ZONE = "is_in_safe_zone"
ATTR_LAST_SEEN = "last_seen"
ATTR_LOCATE_TYPE = "locate_type"
ATTR_POI = "poi"
ATTR_PROVINCE = "province"
ATTR_SAFE_ZONE_LABEL = "safe_zone_label"
