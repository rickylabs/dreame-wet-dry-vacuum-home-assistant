"""Button platform for Dreame wet & dry vacuum (one-shot commands)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DreameWetDryConfigEntry
from .const import KNOWN_BUTTON_PROPS
from .entity import DreameWetDryEntity
from .h15 import async_start_self_clean, dirty_tank_full


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DreameWetDryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    # Only commands checked on this model; untested models get none.
    async_add_entities(
        DreameWetDryButton(coordinator, key, meta)
        for key, meta in KNOWN_BUTTON_PROPS.items()
        if key in coordinator.profile.button_keys
    )


def _guarded_self_clean(coordinator) -> bool:
    """H15 Mix: self-clean goes through the checked start sequence."""
    return coordinator.profile.key == "h15_mix"


class DreameWetDryButton(DreameWetDryEntity, ButtonEntity):
    """Sends a fixed value to a property when pressed."""

    def __init__(self, coordinator, key, meta) -> None:
        super().__init__(coordinator, key, meta)
        self._press_value = meta.get("press_value", 1)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if _guarded_self_clean(self.coordinator):
            status = self.coordinator.props.get((2, 1))
            return (
                bool(self.coordinator.snapshot.get("online"))
                and status in (4, 15)
                and not dirty_tank_full(self.coordinator)
            )
        return True

    async def async_press(self) -> None:
        if _guarded_self_clean(self.coordinator):
            try:
                await async_start_self_clean(self.coordinator)
            except RuntimeError as err:
                raise HomeAssistantError(str(err)) from err
            return
        await self._set(self._press_value)
