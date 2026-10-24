# Dreame Wet & Dry Vacuum for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/rickylabs/dreame-wet-dry-vacuum-home-assistant/actions/workflows/validate.yml/badge.svg)](https://github.com/rickylabs/dreame-wet-dry-vacuum-home-assistant/actions/workflows/validate.yml)

A custom [Home Assistant](https://www.home-assistant.io/) integration for **Dreame wet & dry stick vacuums**. It logs in to the Dreame cloud with your Dreamehome account, gets live updates through the cloud MQTT feed, and polls the cloud every 5 minutes as a fallback.

This is a fork of [morcus/dreame-wet-dry-vacuum-home-assistant](https://github.com/morcus/dreame-wet-dry-vacuum-home-assistant). See [Credits](#credits).

> This is an **unofficial** integration. It is not made, endorsed or supported by Dreame. The cloud API is undocumented and can change at any time.

## Supported models

| Model | Model id | Status | What you get |
|---|---|---|---|
| H14 Pro | `dreame.hold.w2306e` | Tested | Sensors, alerts, switches, numbers, selects, self-clean and self-dry buttons |
| H15 Mix | `dreame.hold.w2506` | Tested by the author of upstream PR #8 | Sensors, alerts, Start self-cleaning button |
| H15 Pro Heat | `dreame.hold.w2449e`, `dreame.hold.w2449g` | **Untested** (state codes from @matanmesika's captures) | Read-only: state, work mode, battery, brush and filter life |
| Any other `dreame.hold.*` | | **Untested** | Read-only: state, battery, work mode code |

Untested models never get controls. Unknown state codes show as `Status <number>` instead of failing. The first time the integration sees an untested model or an unknown state code, it logs the model id and the code once (no account data).

If you own an untested model, please [send diagnostics](#send-diagnostics) in an issue so it can be mapped.

## Entities

This is a stick vacuum, not a robot, so there is **no `vacuum` entity**.

- **Sensors:** state, battery, washing and drying progress, totals and last clean, brush and filter life, water level, suction mode.
- **Binary sensors:** online, charging, and tank and detergent alerts.
- **Switches, numbers, selects (H14 Pro only):** light, auto detergent, auto rinse, auto dry, voice volume, custom mode, traction force.
- **Buttons:** start self-cleaning (H14 Pro, H15 Mix) and start self-drying (H14 Pro).

Some controls are optimistic: the device does not report them back, so the entity shows the last value you sent. Names are translated into English, French and German.

### H15 Mix notes

Only **Start self-cleaning** is exposed. It works while the device is online and charging, unless the **Dirty water tank full** alert is on. Fill the clean-water tank and seat an empty dirty-water tank first, as the [H15 Mix manual](https://global.dreametech.com/pages/h15-mix-user-manual-1) says. After emptying the tank, the cloud can take a few minutes to clear the alert.

## Requirements

- Home Assistant **2025.1** or newer.
- A Dreamehome account with the vacuum already added in the app.
- Regions: `eu`, `cn`, `us`, `sg`, `ru`, `kr`.

## Installation

### HACS

1. In HACS, open **⋮ → Custom repositories**.
2. Add `https://github.com/rickylabs/dreame-wet-dry-vacuum-home-assistant` with the category **Integration**.
3. Download **Dreame Wet & Dry Vacuum**, then restart Home Assistant.

### Manual

Copy `custom_components/dreame_wet_dry_vacuum/` into your `config/custom_components/` folder, then restart Home Assistant.

## Setup

1. **Settings → Devices & services → Add integration → Dreame Wet & Dry Vacuum**.
2. Enter your Dreamehome email, password and region. If the device list is empty, try another region: a login can succeed on the wrong region and list nothing. Israel and Middle-East accounts are usually on `sg`.
3. If the account has more than one wet & dry vacuum, pick one.

If the password changes, Home Assistant asks you to sign in again.

## Send diagnostics

1. **Settings → Devices & services → Dreame Wet & Dry Vacuum**.
2. Open the **⋮** menu on the entry, then **Download diagnostics**.
3. Attach the file to a GitHub issue.

The file holds the model id, the profile, the raw state values and the firmware version. Your email, password, tokens, account id, device id, serial number, MAC address, network details and device name are replaced by `**REDACTED**`. Read the file before you post it.

For more detail, turn on debug logging:

```yaml
logger:
  logs:
    custom_components.dreame_wet_dry_vacuum: debug
```

## Troubleshooting

- **Invalid email or password:** check that the same login works in the Dreamehome app, and that the region is right.
- **Cannot connect:** Home Assistant cannot reach the Dreame cloud. The integration retries by itself.
- **No device found:** the account has no wet & dry vacuum in the chosen region. Try another region.
- **"Live updates are off" in the log:** the MQTT feed could not start. Values still update every 5 minutes.

## Development

The tests run inside a real Home Assistant core with [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component). They need Python 3.14:

```bash
pip install pytest-homeassistant-custom-component pytest-timeout pycryptodome "paho-mqtt>=2.0" ruff
pytest
ruff check .
```

CI runs hassfest, the HACS check, Ruff and the tests on every push.

The brand icon in `custom_components/dreame_wet_dry_vacuum/brand/` is a generic water drop, not the Dreame logo.

## Credits

- [morcus](https://github.com/morcus): the original integration.
- [Sven Frank (@FiraSenax)](https://github.com/FiraSenax): H15 Mix support (upstream PR #8).
- [Lucas Gasenzer (@luc-ass)](https://github.com/luc-ass): German translation, translatable labels, fixes (upstream PRs #4 to #7).
- [@noambergauz](https://github.com/noambergauz): more cloud regions.
- [Matan Mesika (@matanmesika)](https://github.com/matanmesika): H15 Pro Heat model id, state codes and property map (from his fork's `H15_MAPPING.md`).

## License

Public domain under [The Unlicense](LICENSE).
