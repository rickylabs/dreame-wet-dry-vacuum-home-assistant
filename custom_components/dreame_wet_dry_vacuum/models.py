"""Per-model profiles: which entities a model gets and how its states read.

Each wet & dry model numbers its properties a little differently. A profile
says what is known for one model id. Anything we have not seen loads with the
read-only generic profile, so a new model shows its battery and state instead
of failing, without sending it commands we never checked.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.const import Platform

from .const import (
    DEVICE_STATUS,
    GENERIC_STATUS_EN,
    H14_PRO_MODEL,
    H15_MIX_MODEL,
    H15_MIX_READABLE_PROPS,
    H15_MIX_STATUS_DE,
    H15_MIX_STATUS_EN,
    H15_PRO_HEAT_MODEL,
    H15_PRO_HEAT_MODEL_ALT,
    H15_PRO_HEAT_STATUS_EN,
    STATUS_GROUP,
)

_LOGGER = logging.getLogger(__name__)

ALL_PLATFORMS: tuple[Platform, ...] = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BUTTON,
)
READ_ONLY_PLATFORMS: tuple[Platform, ...] = (Platform.SENSOR, Platform.BINARY_SENSOR)


@dataclass(frozen=True, eq=False)
class ModelProfile:
    """What this integration knows about one model."""

    key: str
    name: str
    # True only for models someone ran this integration against.
    tested: bool
    platforms: tuple[Platform, ...]
    # Sensor properties to create; None means every known property.
    readable_props: frozenset[tuple[int, int]] | None
    # Alert binary sensors (ALERT_BINARY_SENSORS keys); None means all of them.
    alert_keys: frozenset[str] | None
    # Create the generic property binary sensors (KNOWN_BINARY_PROPS).
    prop_binaries: bool
    # Buttons (KNOWN_BUTTON_PROPS keys) to create.
    button_keys: frozenset[tuple[int, int]]
    # Status names by language ("" is the fallback table).
    status_labels: Mapping[str, Mapping[int, str]]
    # Also show 1.28 (work mode) with the status names.
    work_mode_labels: bool
    status_groups: Mapping[int, str]
    # Assume a 60 h life when the device does not report the full life.
    consumable_fallback: bool


H14_PRO = ModelProfile(
    key="h14_pro",
    name="H14 Pro",
    tested=True,
    platforms=ALL_PLATFORMS,
    readable_props=None,
    alert_keys=None,
    prop_binaries=True,
    button_keys=frozenset({(1, 1), (1, 2)}),
    status_labels={"": DEVICE_STATUS},
    work_mode_labels=False,
    status_groups=STATUS_GROUP,
    consumable_fallback=True,
)

H15_MIX = ModelProfile(
    key="h15_mix",
    name="H15 Mix",
    tested=True,
    platforms=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON),
    readable_props=frozenset(H15_MIX_READABLE_PROPS),
    alert_keys=frozenset({"dirty_tank_full"}),
    prop_binaries=False,
    button_keys=frozenset({(1, 1)}),
    status_labels={"": H15_MIX_STATUS_EN, "de": H15_MIX_STATUS_DE},
    work_mode_labels=False,
    status_groups=STATUS_GROUP,
    consumable_fallback=True,
)

# From Matan Mesika's H15 Pro Heat captures (see const.py). Read-only until
# someone runs this integration against the device.
H15_PRO_HEAT = ModelProfile(
    key="h15_pro_heat",
    name="H15 Pro Heat",
    tested=False,
    platforms=READ_ONLY_PLATFORMS,
    readable_props=frozenset({(2, 1), (3, 1), (1, 28), (6, 7), (19, 3)}),
    alert_keys=frozenset({"dirty_tank_full"}),
    prop_binaries=False,
    button_keys=frozenset(),
    status_labels={"": H15_PRO_HEAT_STATUS_EN},
    work_mode_labels=True,
    status_groups={
        **STATUS_GROUP,
        **dict.fromkeys((30, 31, 36, 37, 42, 43), "self_cleaning"),
        **dict.fromkeys((32, 33, 34, 35), "drying"),
        **dict.fromkeys((40, 41), "mopping"),
    },
    consumable_fallback=False,
)

GENERIC = ModelProfile(
    key="generic",
    name="Generic",
    tested=False,
    platforms=READ_ONLY_PLATFORMS,
    readable_props=frozenset({(2, 1), (3, 1), (1, 28)}),
    alert_keys=frozenset(),
    prop_binaries=False,
    button_keys=frozenset(),
    status_labels={"": GENERIC_STATUS_EN},
    work_mode_labels=False,
    status_groups={code: group for code, group in STATUS_GROUP.items() if code <= 15},
    consumable_fallback=False,
)

PROFILES: dict[str, ModelProfile] = {
    H14_PRO_MODEL: H14_PRO,
    H15_MIX_MODEL: H15_MIX,
    H15_PRO_HEAT_MODEL: H15_PRO_HEAT,
    H15_PRO_HEAT_MODEL_ALT: H15_PRO_HEAT,
}

# Log each untested model and each unknown status code once per run.
_logged_models: set[str] = set()
_logged_status: set[tuple[str, int]] = set()


def get_profile(model: str | None) -> ModelProfile:
    """Return the profile for a model id, or the generic one."""
    model = model or ""
    profile = PROFILES.get(model, GENERIC)
    if not profile.tested and model not in _logged_models:
        _logged_models.add(model)
        _LOGGER.info(
            "Dreame model %s is not tested with this integration; it loads "
            "read-only with the %s profile. Diagnostics from this device help "
            "add it",
            model or "(unknown)",
            profile.name,
        )
    return profile


def status_code(raw: Any) -> int | None:
    """Status value as an int, or None when it is missing or not a number."""
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def status_group(profile: ModelProfile, raw: Any) -> str | None:
    """Coarse state group (charging, mopping...) for a status value."""
    code = status_code(raw)
    if code is None:
        return None
    return profile.status_groups.get(code, "unknown")


def describe_status(
    profile: ModelProfile, model: str | None, raw: Any, language: str = "en"
) -> str | None:
    """Readable name for a status value; "Status N" when the code is unknown."""
    if raw is None:
        return None
    code = status_code(raw)
    if code is None:
        return str(raw)
    labels = profile.status_labels.get(
        (language or "")[:2].lower(), profile.status_labels[""]
    )
    label = labels.get(code)
    if label is not None:
        return label
    seen = (model or "", code)
    if seen not in _logged_status:
        _logged_status.add(seen)
        _LOGGER.info(
            "Dreame model %s reported status %s, which this integration does not know yet",
            model or "(unknown)",
            code,
        )
    return f"Status {code}"
