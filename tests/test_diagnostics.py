"""Diagnostics: account and device identifiers are removed, useful values stay."""
from __future__ import annotations

import json

from homeassistant.core import HomeAssistant

from custom_components.dreame_wet_dry_vacuum.const import H15_PRO_HEAT_MODEL
from custom_components.dreame_wet_dry_vacuum.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .common import (
    BIND_DOMAIN,
    CUSTOM_NAME,
    DID,
    FIRMWARE,
    MAC,
    PASSWORD,
    SERIAL,
    TOKEN,
    UID,
    USERNAME,
    device_record,
    make_api,
    setup_entry,
)

LOCAL_IP = "192.0.2.44"  # documentation range, not a real address
SSID = "not-a-real-wifi"
REDACTED = "**REDACTED**"

# Every made-up identifier that goes into the entry or the device record.
SEEDED = (
    USERNAME,
    PASSWORD,
    DID,
    MAC,
    SERIAL,
    BIND_DOMAIN.split(":")[0],
    CUSTOM_NAME,
    LOCAL_IP,
    SSID,
)


async def _diagnostics(hass: HomeAssistant):
    record = device_record(
        H15_PRO_HEAT_MODEL,
        latestStatus=42,
        network={"localip": LOCAL_IP, "ssid": SSID},
    )
    api = make_api(record)
    api.get_status_props.return_value = {"6.7": 1200}
    entry = await setup_entry(hass, api, H15_PRO_HEAT_MODEL)
    coordinator = entry.runtime_data
    raw = json.dumps([dict(entry.data), coordinator.device_info_raw, coordinator.snapshot])
    result = await async_get_config_entry_diagnostics(hass, entry)
    return raw, result


async def test_identifiers_are_removed(hass: HomeAssistant, mqtt_client) -> None:
    raw, result = await _diagnostics(hass)
    out = json.dumps(result)
    # Control: the values really were in what diagnostics read from.
    for value in SEEDED:
        assert value in raw, value
    for value in (*SEEDED, TOKEN, UID):
        assert value not in out, value
    # Keys stay, so the reader sees what was removed.
    assert result["entry"]["data"]["password"] == REDACTED
    assert result["device"]["mac"] == REDACTED
    assert result["device"]["network"]["localip"] == REDACTED


async def test_useful_values_are_kept(hass: HomeAssistant, mqtt_client) -> None:
    _, result = await _diagnostics(hass)
    assert result["model"] == H15_PRO_HEAT_MODEL
    assert result["profile"]["key"] == "h15_pro_heat"
    assert result["profile"]["tested"] is False
    assert result["entry"]["data"]["region"] == "eu"
    assert result["entry"]["data"]["device_model"] == H15_PRO_HEAT_MODEL
    assert result["device"]["ver"] == FIRMWARE
    assert result["device"]["battery"] == 87
    assert result["device"]["deviceInfo"]["model"] == H15_PRO_HEAT_MODEL
    assert result["snapshot"]["firmware"] == FIRMWARE
    assert result["props"]["2.1"] == 42
    assert result["props"]["3.1"] == 87
    assert result["props"]["6.7"] == 1200
    assert result["mqtt_connected"] is True
