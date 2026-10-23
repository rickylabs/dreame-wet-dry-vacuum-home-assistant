"""Shared fixtures (pytest-homeassistant-custom-component)."""
from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.dreame_wet_dry_vacuum import models


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Let Home Assistant load custom_components/ in every test."""


@pytest.fixture(autouse=True)
def reset_log_once() -> Generator[None]:
    """Each test starts with the "log once" sets empty."""
    models._logged_models.clear()
    models._logged_status.clear()
    yield
    models._logged_models.clear()
    models._logged_status.clear()


@pytest.fixture
def mqtt_client() -> Generator[MagicMock]:
    """Replace the MQTT client class: no thread, no socket."""
    with patch(
        "custom_components.dreame_wet_dry_vacuum.coordinator.DreameMqttClient"
    ) as client_cls:
        client_cls.return_value.connected = True
        yield client_cls
