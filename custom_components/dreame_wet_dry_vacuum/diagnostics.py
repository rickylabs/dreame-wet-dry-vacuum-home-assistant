"""Diagnostics for Dreame wet & dry vacuum.

The download is meant to be posted in a public issue when a model is not
known yet, so account and device identifiers are removed. Model id, state
values and property numbers stay: those are what is needed to add a model.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import DreameWetDryConfigEntry

# Matched at any depth (async_redact_data walks nested dicts and lists).
TO_REDACT = {
    # account
    "username",
    "email",
    "password",
    "access_token",
    "refresh_token",
    "token",
    "uid",
    "masterUid",
    "masterName",
    "ownerId",
    "nickName",
    "phone",
    # device identity and location
    "did",
    "device_id",
    "deviceId",
    "device_name",
    "mac",
    "sn",
    "serial",
    "serialNumber",
    "bindDomain",
    "bind_domain",
    "customName",
    "displayName",
    "name",
    "ip",
    "localip",
    "ssid",
    "bssid",
    "lat",
    "lon",
    "latitude",
    "longitude",
    "city",
    "address",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DreameWetDryConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    profile = coordinator.profile
    return {
        "entry": {
            "title": "**REDACTED**",
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "model": coordinator.model,
        "profile": {
            "key": profile.key,
            "name": profile.name,
            "tested": profile.tested,
            "platforms": [str(platform) for platform in profile.platforms],
        },
        "mqtt_connected": bool(coordinator.mqtt and coordinator.mqtt.connected),
        "props": {
            f"{siid}.{piid}": value
            for (siid, piid), value in sorted(coordinator.props.items())
        },
        "snapshot": async_redact_data(dict(coordinator.snapshot), TO_REDACT),
        "device": async_redact_data(dict(coordinator.device_info_raw), TO_REDACT),
    }
