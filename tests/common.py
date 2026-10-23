"""Test helpers: a fake Dreame cloud and config entries."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dreame_wet_dry_vacuum.const import (
    CONF_DEVICE_ID,
    CONF_REGION,
    DOMAIN,
    H14_PRO_MODEL,
)

# Made-up account and device values. The diagnostics tests check that none of
# them comes back out.
USERNAME = "owner@example.invalid"
PASSWORD = "pw-not-real-123"
TOKEN = "token-not-real-456"
UID = "uid-not-real-789"
DID = "-987654321"
MAC = "AA:BB:CC:00:11:22"
SERIAL = "SN-NOT-REAL-0042"
BIND_DOMAIN = "10000.mt.eu.broker.invalid:19973"
CUSTOM_NAME = "Kitchen floor washer"
FIRMWARE = "4.3.9_0123"


def device_record(model: str = H14_PRO_MODEL, **extra: Any) -> dict[str, Any]:
    """One record as the Dreame device list returns it."""
    record = {
        "did": DID,
        "model": model,
        "mac": MAC,
        "sn": SERIAL,
        "ver": FIRMWARE,
        "battery": 87,
        "latestStatus": 1,
        "online": True,
        "bindDomain": BIND_DOMAIN,
        "customName": CUSTOM_NAME,
        "masterName": USERNAME,
        "deviceInfo": {"displayName": CUSTOM_NAME, "model": model},
    }
    record.update(extra)
    return record


def snapshot_for(record: dict[str, Any]) -> dict[str, Any]:
    """What DreameAPI.get_device_snapshot builds from a record."""
    return {
        "battery": record.get("battery"),
        "status": record.get("latestStatus"),
        "online": record.get("online"),
        "model": record.get("model"),
        "name": CUSTOM_NAME,
        "firmware": record.get("ver"),
        "mac": record.get("mac"),
    }


def make_api(record: dict[str, Any] | None = None) -> MagicMock:
    """A DreameAPI stand-in that answers like a healthy cloud."""
    record = device_record() if record is None else record
    api = MagicMock()
    api.uid = UID
    api.access_token = TOKEN
    api.region = "eu"
    api.login = AsyncMock()
    api.get_devices = AsyncMock(return_value=[record])
    api.get_device_snapshot = AsyncMock(return_value=snapshot_for(record))
    api.get_status_props = AsyncMock(return_value={})
    api.set_property = AsyncMock(return_value=True)
    api.call_action = AsyncMock(return_value=True)
    return api


def make_entry(model: str = H14_PRO_MODEL) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=CUSTOM_NAME,
        unique_id=DID,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_REGION: "eu",
            CONF_DEVICE_ID: DID,
            "device_model": model,
            "device_name": CUSTOM_NAME,
        },
    )


async def setup_entry(
    hass: HomeAssistant, api: MagicMock, model: str = H14_PRO_MODEL
) -> MockConfigEntry:
    """Add an entry and set it up against the fake cloud."""
    entry = make_entry(model)
    entry.add_to_hass(hass)
    with patch("custom_components.dreame_wet_dry_vacuum.DreameAPI", return_value=api):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry
