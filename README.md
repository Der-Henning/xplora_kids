# Xplora Kids for Home Assistant

Custom Home Assistant integration for Xplora kids watches.

This repository is intentionally small: it exposes the essentials for one or
more watches attached to a parent Xplora account.

- `device_tracker` per watch with GPS location, accuracy, battery level, and
  location attributes.
- Sensors per watch for battery, steps, location accuracy, distance, locate
  type, safe-zone label, and last seen time.
- Binary sensors per watch for charging, safe-zone status, and adjusted
  location status.
- Button per watch to request an immediate location refresh.
- Config flow setup from the Home Assistant UI.
- Optional polling setting to ask the watch for a fresh location on every poll.
- Configurable cooldown for manual and automatic fresh location requests.
- Redacted diagnostics for troubleshooting.
- English and German UI translations.
- English and German entity-name translations.
- Official Xplora brand assets in `custom_components/xplora_kids/brand/`.

## Why This Exists

There is an older custom integration, `Ludy87/xplora_watch`, but it was archived
after Xplora started blocking the application by IP ban. The lower-level
`pyxplora_api` project still documents the GraphQL API shape, so this integration
uses only the small subset needed for location, battery, and watch status.

## Installation

Copy `custom_components/xplora_kids` into your Home Assistant config directory:

```text
/config/custom_components/xplora_kids
```

Restart Home Assistant, then add **Xplora Kids** from **Settings > Devices &
services > Add integration**.

You can sign in with either:

- email and password, or
- country code, phone number, and password.

For German phone login, enter `49` as country code and the phone number without
the country code.

## Options

After setup, open the integration options:

- `scan_interval`: default `300` seconds.
- `request_location`: default off. When enabled, Home Assistant asks each watch
  to refresh its own location on every poll. This may increase API usage and
  watch battery usage.
- `location_request_cooldown`: default `60` seconds. Applies to both the
  request-location button and automatic fresh location requests.
- Optional per-watch MAC address fields: enter the MAC address shown by router
  integrations such as FRITZ!Box Tools to let Home Assistant associate the
  Xplora entities with the same device registry device. Reload the integration
  after setting a MAC address; if Home Assistant already created duplicate
  device registry entries, removing the older duplicate device may be necessary.
  To remove a manually configured MAC address, clear the matching field and
  save the options. The integration removes the previous Xplora-configured MAC
  connection from the device registry during the reload.

## Diagnostics

Home Assistant can download redacted diagnostics from the integration entry or
device page. The diagnostics include configuration shape, update status, and API
payload keys, but redact account credentials, phone details, MAC addresses,
watch identifiers, exact coordinates, and address data.

## Notes

This uses an unofficial API. Xplora can change or block it at any time. Keep the
polling interval reasonable, especially if you enable forced location refreshes.
If one watch cannot be updated temporarily, the integration keeps successful
watch updates available and marks only the affected watch entities unavailable.

Xplora appears to allow only one active login session per parent account. Signing
in with the official Xplora phone app can invalidate the Home Assistant session,
and Home Assistant may invalidate the phone app session when it signs in again.
If this becomes annoying, create a dedicated Xplora parent account for this
integration and grant that account access to the children's watches.
