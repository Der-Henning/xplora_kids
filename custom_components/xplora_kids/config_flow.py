"""Config flow for Xplora Kids."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import XploraApi, XploraApiError, XploraAuthenticationError
from .const import (
    CONF_COUNTRY_CODE,
    CONF_LOCATION_REQUEST_COOLDOWN,
    CONF_PHONE_NUMBER,
    CONF_REQUEST_LOCATION,
    CONF_SCAN_INTERVAL,
    CONF_TIME_ZONE,
    CONF_USER_LANGUAGE,
    CONF_WATCH_MACS,
    DEFAULT_LOCATION_REQUEST_COOLDOWN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIME_ZONE,
    DEFAULT_USER_LANGUAGE,
    DATA_COORDINATOR,
    DOMAIN,
)
from .helpers import clean_optional_text, normalize_mac

MIN_SCAN_INTERVAL = 60
MIN_LOCATION_REQUEST_COOLDOWN = 15


class XploraKidsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Xplora Kids config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _normalize_input(user_input)
            errors = _validate_login_fields(data)

            if not errors:
                validation_error, api = await _validate_credentials(self.hass, data)
                if validation_error:
                    errors["base"] = validation_error
                elif api is not None:
                    unique_id = api.account_id or data.get(CONF_EMAIL) or data.get(CONF_PHONE_NUMBER)
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    title = api.account_name or data.get(CONF_EMAIL) or "Xplora Kids"
                    return self.async_create_entry(
                        title=title,
                        data=data,
                        options={
                            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                            CONF_REQUEST_LOCATION: False,
                            CONF_LOCATION_REQUEST_COOLDOWN: DEFAULT_LOCATION_REQUEST_COOLDOWN,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(self.hass, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> config_entries.FlowResult:
        """Handle re-authentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Ask for the updated password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = dict(self._reauth_entry.data)
            data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
            validation_error, _api = await _validate_credentials(self.hass, data)
            if validation_error:
                errors["base"] = validation_error
            else:
                self.hass.config_entries.async_update_entry(self._reauth_entry, data=data)
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return XploraKidsOptionsFlow(config_entry)


class XploraKidsOptionsFlow(config_entries.OptionsFlow):
    """Handle Xplora Kids options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._mac_fields: dict[str, str] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        """Manage options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            options, errors = self._parse_options(user_input)
            if not errors:
                return self.async_create_entry(title="", data=options)

        options = self._config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=self._options_schema(options, user_input),
            errors=errors,
        )

    def _options_schema(
        self,
        options: Mapping[str, Any],
        user_input: dict[str, Any] | None,
    ) -> vol.Schema:
        """Return the options schema."""
        user_input = user_input or {}
        watch_macs = options.get(CONF_WATCH_MACS, {})
        schema: dict[vol.Marker, Any] = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=user_input.get(
                    CONF_SCAN_INTERVAL,
                    options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
            vol.Optional(
                CONF_REQUEST_LOCATION,
                default=user_input.get(CONF_REQUEST_LOCATION, options.get(CONF_REQUEST_LOCATION, False)),
            ): bool,
            vol.Optional(
                CONF_LOCATION_REQUEST_COOLDOWN,
                default=user_input.get(
                    CONF_LOCATION_REQUEST_COOLDOWN,
                    options.get(CONF_LOCATION_REQUEST_COOLDOWN, DEFAULT_LOCATION_REQUEST_COOLDOWN),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_LOCATION_REQUEST_COOLDOWN)),
        }

        self._mac_fields = {}
        for watch_id, watch_name in self._watch_names().items():
            field = f"{watch_name} MAC address"
            if field in self._mac_fields:
                field = f"{watch_name} MAC address ({watch_id[-6:]})"
            self._mac_fields[field] = watch_id
            schema[
                vol.Optional(
                    field,
                    default=user_input.get(field, watch_macs.get(watch_id, "")),
                )
            ] = str

        return vol.Schema(schema)

    def _parse_options(self, user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        """Parse and validate options form input."""
        if not self._mac_fields:
            self._options_schema(self._config_entry.options, None)

        errors: dict[str, str] = {}
        watch_macs: dict[str, str] = {}

        for field, watch_id in self._mac_fields.items():
            value = clean_optional_text(user_input.get(field))
            if not value:
                continue
            mac_address = normalize_mac(value)
            if mac_address is None:
                errors[field] = "invalid_mac"
                continue
            watch_macs[watch_id] = mac_address

        options = {
            CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
            CONF_REQUEST_LOCATION: user_input[CONF_REQUEST_LOCATION],
            CONF_LOCATION_REQUEST_COOLDOWN: user_input[CONF_LOCATION_REQUEST_COOLDOWN],
        }
        if watch_macs:
            options[CONF_WATCH_MACS] = watch_macs
        return options, errors

    def _watch_names(self) -> dict[str, str]:
        """Return configured watches keyed by Xplora watch id."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id, {})
        coordinator = entry_data.get(DATA_COORDINATOR)
        if coordinator is None:
            return {}
        return {watch.id: watch.name for watch in coordinator.api.watches}


async def _validate_credentials(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> tuple[str | None, XploraApi | None]:
    """Validate credentials with Xplora."""
    api = XploraApi(
        async_get_clientsession(hass),
        email=data.get(CONF_EMAIL),
        country_code=data.get(CONF_COUNTRY_CODE),
        phone_number=data.get(CONF_PHONE_NUMBER),
        password=data[CONF_PASSWORD],
        user_language=data[CONF_USER_LANGUAGE],
        time_zone=data[CONF_TIME_ZONE],
    )

    try:
        watches = await api.async_validate_credentials()
    except XploraAuthenticationError:
        return "invalid_auth", None
    except XploraApiError:
        return "cannot_connect", None
    except Exception:
        return "unknown", None

    if not watches:
        return "no_watches", None

    return None, api


def _user_schema(hass: HomeAssistant, user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Return the initial config flow schema."""
    user_input = user_input or {}
    default_time_zone = getattr(hass.config, "time_zone", None) or DEFAULT_TIME_ZONE

    return vol.Schema(
        {
            vol.Optional(CONF_EMAIL, default=user_input.get(CONF_EMAIL, "")): str,
            vol.Optional(CONF_COUNTRY_CODE, default=user_input.get(CONF_COUNTRY_CODE, "")): str,
            vol.Optional(CONF_PHONE_NUMBER, default=user_input.get(CONF_PHONE_NUMBER, "")): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(
                CONF_USER_LANGUAGE,
                default=user_input.get(CONF_USER_LANGUAGE, DEFAULT_USER_LANGUAGE),
            ): str,
            vol.Optional(
                CONF_TIME_ZONE,
                default=user_input.get(CONF_TIME_ZONE, default_time_zone),
            ): str,
        }
    )


def _normalize_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize config flow input."""
    data = dict(user_input)
    data[CONF_EMAIL] = clean_optional_text(data.get(CONF_EMAIL))
    data[CONF_COUNTRY_CODE] = clean_optional_text(data.get(CONF_COUNTRY_CODE), strip_plus=True)
    data[CONF_PHONE_NUMBER] = clean_optional_text(data.get(CONF_PHONE_NUMBER), strip_spaces=True)
    data[CONF_USER_LANGUAGE] = data.get(CONF_USER_LANGUAGE) or DEFAULT_USER_LANGUAGE
    data[CONF_TIME_ZONE] = data.get(CONF_TIME_ZONE) or DEFAULT_TIME_ZONE
    return data


def _validate_login_fields(data: dict[str, Any]) -> dict[str, str]:
    """Validate that either email or phone credentials are present."""
    if data.get(CONF_EMAIL):
        return {}
    if data.get(CONF_COUNTRY_CODE) and data.get(CONF_PHONE_NUMBER):
        return {}
    return {"base": "missing_auth"}
