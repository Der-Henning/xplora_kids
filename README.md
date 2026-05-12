# Xplora Kids for Home Assistant

Custom Home Assistant integration for Xplora kids watches.

This repository is intentionally small: it exposes the essentials for one or
more watches attached to a parent Xplora account.

- `device_tracker` per watch with GPS location, accuracy, battery level, and
  location attributes.
- `sensor` per watch for battery percentage.
- `sensor` per watch for today's step count.
- Config flow setup from the Home Assistant UI.
- Optional polling setting to ask the watch for a fresh location on every poll.
- English and German UI translations.
- Official Xplora logotype in `custom_components/xplora_kids/brand/logo.png`.

## Why This Exists

There is an older custom integration, `Ludy87/xplora_watch`, but it was archived
after Xplora started blocking the application by IP ban. The lower-level
`pyxplora_api` project still documents the GraphQL API shape, so this integration
uses only the small subset needed for location and battery.

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

## Notes

This uses an unofficial API. Xplora can change or block it at any time. Keep the
polling interval reasonable, especially if you enable forced location refreshes.

## Logo

The integration logo is the Xplora logotype from the Xplora US shop CDN:

```text
https://shop.myxplora.com/cdn/shop/files/Xplora_logotype_Black_RGB_2_682x228_crop_center.png?v=1614296501
```

No generated icon is included.
