"""Setup, unload and bad cloud replies, against a fake cloud (no network)."""
from __future__ import annotations

import logging
from typing import Any

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from custom_components.dreame_wet_dry_vacuum.api import DreameAPIError, DreameAuthError
from custom_components.dreame_wet_dry_vacuum.const import DOMAIN

from .common import (
    DID,
    PASSWORD,
    TOKEN,
    UID,
    USERNAME,
    device_record,
    make_api,
    setup_entry,
)

UNKNOWN_MODEL = "dreame.hold.w9999z"
OUR_LOGGER = "custom_components.dreame_wet_dry_vacuum"


def _entries(hass: HomeAssistant, entry) -> list[er.RegistryEntry]:
    return er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


def _state(hass: HomeAssistant, domain: str, key: str) -> State:
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{DID}_{key}")
    assert entity_id is not None, f"no {domain} entity for {key}"
    state = hass.states.get(entity_id)
    assert state is not None
    return state


def _reauth_flows(hass: HomeAssistant, entry) -> list[Any]:
    return list(entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


def _our_messages(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name.startswith(OUR_LOGGER)]


async def test_h14_setup_and_unload(hass: HomeAssistant, mqtt_client) -> None:
    entry = await setup_entry(hass, make_api())
    assert entry.state is ConfigEntryState.LOADED
    coordinator = entry.runtime_data
    assert {e.domain for e in _entries(hass, entry)} >= {
        "sensor",
        "binary_sensor",
        "button",
        "switch",
    }
    assert _state(hass, "sensor", "3.1").state == "87"
    mqtt_client.return_value.start.assert_called_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert mqtt_client.return_value.stop.called
    assert coordinator.stopping is True
    assert coordinator._unsub_poll is None


async def test_unique_ids_keep_their_format(hass: HomeAssistant, mqtt_client) -> None:
    """Entity ids from earlier versions must still match after an update."""
    entry = await setup_entry(hass, make_api())
    unique_ids = {e.unique_id for e in _entries(hass, entry)}
    assert {
        f"{DID}_2.1",
        f"{DID}_3.1",
        f"{DID}_online",
        f"{DID}_charging",
        f"{DID}_consumable_front_brush",
    } <= unique_ids
    assert all(uid.startswith(f"{DID}_") for uid in unique_ids)


async def test_unknown_model_loads_read_only(
    hass: HomeAssistant, mqtt_client, caplog
) -> None:
    caplog.set_level(logging.INFO, logger=OUR_LOGGER)
    api = make_api(device_record(UNKNOWN_MODEL, latestStatus=77))
    entry = await setup_entry(hass, api, UNKNOWN_MODEL)
    assert entry.state is ConfigEntryState.LOADED

    domains = {e.domain for e in _entries(hass, entry)}
    assert "sensor" in domains
    assert domains <= {"sensor", "binary_sensor"}
    assert _state(hass, "sensor", "2.1").state == "Status 77"

    # A second poll must not log the model or the code again.
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    messages = _our_messages(caplog)
    assert len([m for m in messages if UNKNOWN_MODEL in m and "not tested" in m]) == 1
    assert len([m for m in messages if "status 77" in m]) == 1


async def test_logs_hold_no_account_data(
    hass: HomeAssistant, mqtt_client, caplog
) -> None:
    caplog.set_level(logging.DEBUG, logger=OUR_LOGGER)
    api = make_api(device_record(UNKNOWN_MODEL, latestStatus=77))
    api.get_status_props.side_effect = DreameAPIError("Request failed (500)")
    entry = await setup_entry(hass, api, UNKNOWN_MODEL)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    text = "\n".join(_our_messages(caplog))
    # Positive control: our log lines were captured at all.
    assert UNKNOWN_MODEL in text
    assert "status_props poll failed" in text
    for private in (USERNAME, PASSWORD, TOKEN, UID, DID):
        assert private not in text


async def test_rejected_login_starts_reauth(hass: HomeAssistant, mqtt_client) -> None:
    api = make_api()
    api.login.side_effect = DreameAuthError("Login rejected (401)")
    entry = await setup_entry(hass, api)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert len(_reauth_flows(hass, entry)) == 1
    mqtt_client.assert_not_called()


@pytest.mark.parametrize("step", ["login", "get_devices", "get_device_snapshot"])
async def test_cloud_down_retries_later(
    hass: HomeAssistant, mqtt_client, step
) -> None:
    api = make_api()
    getattr(api, step).side_effect = DreameAPIError("Request failed (503)")
    entry = await setup_entry(hass, api)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert _reauth_flows(hass, entry) == []


@pytest.mark.parametrize(
    "devices", [[], [device_record(did="-111")], [{"model": "dreame.hold.w2306e"}]]
)
async def test_device_missing_retries_later(
    hass: HomeAssistant, mqtt_client, devices
) -> None:
    api = make_api()
    api.get_devices.return_value = devices
    entry = await setup_entry(hass, api)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("snapshot", [{}, None])
@pytest.mark.parametrize(
    "props",
    [{}, None, ["2.1"], {"bad": 1, "4": 2}, DreameAPIError("Request failed (500)")],
)
async def test_empty_cloud_replies_still_load(
    hass: HomeAssistant, mqtt_client, snapshot, props
) -> None:
    api = make_api()
    api.get_device_snapshot.return_value = snapshot
    if isinstance(props, Exception):
        api.get_status_props.side_effect = props
    else:
        api.get_status_props.return_value = props
    entry = await setup_entry(hass, api)
    assert entry.state is ConfigEntryState.LOADED
    coordinator = entry.runtime_data
    assert coordinator.last_update_success
    assert coordinator.props == {}
    assert _state(hass, "sensor", "3.1").state == "unknown"


async def test_good_keys_survive_bad_ones(hass: HomeAssistant, mqtt_client) -> None:
    api = make_api()
    api.get_status_props.return_value = {"bad": 1, "6.7": 1200, "4": 2}
    entry = await setup_entry(hass, api)
    assert entry.runtime_data.props[(6, 7)] == 1200


async def test_later_cloud_error_keeps_last_values(
    hass: HomeAssistant, mqtt_client
) -> None:
    api = make_api()
    entry = await setup_entry(hass, api)
    coordinator = entry.runtime_data

    api.get_device_snapshot.side_effect = DreameAPIError("Request failed (500)")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success
    assert coordinator.data["3.1"] == 87
    assert _state(hass, "sensor", "3.1").state == "87"


async def test_later_rejected_token_starts_reauth(
    hass: HomeAssistant, mqtt_client
) -> None:
    api = make_api()
    entry = await setup_entry(hass, api)
    coordinator = entry.runtime_data

    api.get_device_snapshot.side_effect = DreameAuthError("Request rejected (401)")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert len(_reauth_flows(hass, entry)) == 1


async def test_new_token_reaches_mqtt_when_snapshot_is_empty(
    hass: HomeAssistant, mqtt_client
) -> None:
    api = make_api()
    entry = await setup_entry(hass, api)
    api.get_device_snapshot.return_value = {}
    api.access_token = "token-after-relogin"
    await entry.runtime_data.async_refresh()
    mqtt_client.return_value.update_token.assert_called_with("token-after-relogin")


async def test_mqtt_start_failure_keeps_polling(
    hass: HomeAssistant, mqtt_client, caplog
) -> None:
    mqtt_client.return_value.start.side_effect = OSError("no route")
    entry = await setup_entry(hass, make_api())
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data._unsub_poll is not None
    assert "live updates are off (OSError)" in caplog.text


async def test_no_bind_domain_means_polling_only(
    hass: HomeAssistant, mqtt_client
) -> None:
    api = make_api(device_record(bindDomain=None))
    entry = await setup_entry(hass, api)
    assert entry.state is ConfigEntryState.LOADED
    mqtt_client.assert_not_called()
    assert entry.runtime_data.mqtt is None
