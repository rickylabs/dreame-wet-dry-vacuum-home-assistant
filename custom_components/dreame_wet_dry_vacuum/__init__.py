"""Dreame wet & dry vacuum integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DreameAPI, DreameAPIError, DreameAuthError
from .const import CONF_DEVICE_ID, CONF_REGION
from .coordinator import DreameWetDryCoordinator
from .models import ALL_PLATFORMS

_LOGGER = logging.getLogger(__name__)

# Every platform this integration has. A model only loads the ones its
# profile lists (see models.py).
PLATFORMS = list(ALL_PLATFORMS)

type DreameWetDryConfigEntry = ConfigEntry[DreameWetDryCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DreameWetDryConfigEntry) -> bool:
    """Set up Dreame wet & dry vacuum from a config entry."""
    api = DreameAPI(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        region=entry.data.get(CONF_REGION, "eu"),
        session=async_get_clientsession(hass),
    )

    try:
        await api.login()
        devices = await api.get_devices()
    except DreameAuthError as err:
        raise ConfigEntryAuthFailed(f"Dreame credentials rejected: {err}") from err
    except DreameAPIError as err:
        raise ConfigEntryNotReady(f"Cannot connect to Dreame cloud: {err}") from err

    device_id = entry.data[CONF_DEVICE_ID]
    device_info = next((d for d in devices if str(d.get("did")) == str(device_id)), {})
    if not device_info:
        raise ConfigEntryNotReady("Dreame device is missing from this account")

    coordinator = DreameWetDryCoordinator(hass, entry, api, device_id, device_info)

    # Raises ConfigEntryNotReady / ConfigEntryAuthFailed on failure
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    coordinator.start_polling()

    # Start the real-time MQTT feed. start() builds an SSL context (blocking
    # disk I/O), so keep it off the event loop.
    # A failure here costs live updates only: the 5-minute poll keeps going.
    try:
        await hass.async_add_executor_job(coordinator.start_mqtt)
    except (OSError, ValueError, RuntimeError) as err:
        _LOGGER.warning(
            "Dreame live updates are off (%s); polling every 5 minutes instead",
            type(err).__name__,
        )
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, coordinator.async_on_ha_stop)
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, coordinator.profile.platforms
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DreameWetDryConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, entry.runtime_data.profile.platforms
    )
    if unloaded:
        coordinator = entry.runtime_data
        coordinator.stopping = True
        coordinator.stop_polling()
        if coordinator.mqtt:
            await hass.async_add_executor_job(coordinator.mqtt.stop)
    return unloaded
