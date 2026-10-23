"""Config flow: login, device choice, errors and reauth."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.dreame_wet_dry_vacuum.api import DreameAPIError, DreameAuthError
from custom_components.dreame_wet_dry_vacuum.const import (
    CONF_DEVICE_ID,
    CONF_REGION,
    DOMAIN,
    H15_PRO_HEAT_MODEL,
)

from .common import DID, PASSWORD, USERNAME, device_record, make_api, make_entry

USER_INPUT = {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_REGION: "eu"}


@pytest.fixture
def flow_api() -> Generator[MagicMock]:
    """Fake cloud used by the config flow."""
    api = make_api(device_record(H15_PRO_HEAT_MODEL))
    with patch(
        "custom_components.dreame_wet_dry_vacuum.config_flow.DreameAPI",
        return_value=api,
    ):
        yield api


@pytest.fixture(autouse=True)
def no_setup() -> Generator[AsyncMock]:
    """Creating an entry must not start the real integration."""
    with patch(
        "custom_components.dreame_wet_dry_vacuum.async_setup_entry",
        return_value=True,
    ) as setup:
        yield setup


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_one_device_creates_entry(hass: HomeAssistant, flow_api) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DID
    assert result["data"][CONF_DEVICE_ID] == DID
    assert result["data"]["device_model"] == H15_PRO_HEAT_MODEL
    assert result["data"][CONF_REGION] == "eu"


async def test_only_wet_dry_models_are_offered(hass: HomeAssistant, flow_api) -> None:
    robot = {"did": "robot-1", "model": "dreame.vacuum.r2209"}
    nameless = {"model": "dreame.hold.w2306e"}  # no device id
    flow_api.get_devices.return_value = [robot, nameless, device_record(H15_PRO_HEAT_MODEL)]
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    # Only one usable wet & dry device is left, so no device step.
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == DID


async def test_several_devices_ask_which_one(hass: HomeAssistant, flow_api) -> None:
    other = device_record("dreame.hold.w2506", did="-111")
    flow_api.get_devices.return_value = [device_record(H15_PRO_HEAT_MODEL), other]
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: "-111"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == "-111"
    assert result["data"]["device_model"] == "dreame.hold.w2506"


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (DreameAuthError("Login rejected (401)"), "invalid_auth"),
        (DreameAPIError("Login failed (503)"), "cannot_connect"),
    ],
)
async def test_login_errors_then_recover(
    hass: HomeAssistant, flow_api, error, key
) -> None:
    flow_api.login.side_effect = error
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": key}

    flow_api.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_device_list_error_is_cannot_connect(hass: HomeAssistant, flow_api) -> None:
    flow_api.get_devices.side_effect = DreameAPIError("Request failed (500)")
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    "devices",
    [[], [{"did": "robot-1", "model": "dreame.vacuum.r2209"}]],
)
async def test_no_wet_dry_devices(hass: HomeAssistant, flow_api, devices) -> None:
    flow_api.get_devices.return_value = devices
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}


async def test_same_device_twice_aborts(hass: HomeAssistant, flow_api) -> None:
    make_entry().add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_password(hass: HomeAssistant, flow_api) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    flow_api.login.side_effect = DreameAuthError("Login rejected (401)")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "still-wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_PASSWORD] == PASSWORD

    flow_api.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"
