"""Builds normalized TelemetrySnapshots from mapped Home Assistant entities.

Normalization rules:
- power values converted to watts (kW -> W)
- battery SOC clamped to 0-100 %
- "unavailable"/"unknown"/unparseable states become None (and are reported
  in missing_roles) instead of failing the whole snapshot
- home load is computed (solar + grid_import - grid_export) when no load
  sensor is mapped; computed fields are listed in estimated_fields
"""

import logging
from datetime import datetime, timezone

from . import database
from .ha_client import HomeAssistantClient
from .models import ROLE_TO_FIELD, TELEMETRY_ROLES, TelemetrySnapshot

logger = logging.getLogger("solar_brain.telemetry")

UNAVAILABLE_STATES = {"unavailable", "unknown", "none", ""}


def _parse_value(state_obj: dict, role: str) -> float | None:
    """Parse and normalize one entity state; None if unusable."""
    entity_id = state_obj.get("entity_id", "?")
    raw = str(state_obj.get("state", "")).strip()
    if raw.lower() in UNAVAILABLE_STATES:
        logger.warning("Entity %s (%s) is %r", entity_id, role, raw or "empty")
        return None
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Entity %s (%s) has non-numeric state %r", entity_id, role, raw)
        return None

    unit = str(state_obj.get("attributes", {}).get("unit_of_measurement", "")).lower()
    if role == "battery_soc":
        if not 0 <= value <= 100:
            logger.warning("Clamping out-of-range SOC %.1f from %s", value, entity_id)
        return max(0.0, min(100.0, value))

    if unit == "kw":
        value *= 1000.0
    if value < 0:
        # Signed grid/solar sensors exist; keep the value but make it visible.
        logger.info("Negative power %.1f W from %s (%s)", value, entity_id, role)
    return value


async def build_snapshot(ha_client: HomeAssistantClient) -> TelemetrySnapshot | None:
    """Build a normalized snapshot from current HA states.

    Returns None when Home Assistant is unreachable/not configured.
    """
    states = await ha_client.get_states()
    if states is None:
        return None

    states_by_id = {s.get("entity_id"): s for s in states}
    mappings = database.get_mappings()

    values: dict[str, float | None] = {}
    missing: list[str] = []
    for role in TELEMETRY_ROLES:
        entity_id = mappings.get(role)
        if not entity_id:
            values[role] = None
            missing.append(role)
            continue
        state_obj = states_by_id.get(entity_id)
        if state_obj is None:
            logger.warning("Mapped entity %s (%s) not found in HA", entity_id, role)
            values[role] = None
            missing.append(role)
            continue
        values[role] = _parse_value(state_obj, role)
        if values[role] is None:
            missing.append(role)

    estimated: list[str] = []
    if values["home_load_power"] is None:
        solar = values["solar_power"]
        imp = values["grid_import_power"]
        exp = values["grid_export_power"]
        if solar is not None and imp is not None and exp is not None:
            values["home_load_power"] = solar + imp - exp
            estimated.append("home_load_w")
            if "home_load_power" in missing:
                missing.remove("home_load_power")

    snapshot = TelemetrySnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        missing_roles=missing,
        estimated_fields=estimated,
        **{ROLE_TO_FIELD[role]: values[role] for role in TELEMETRY_ROLES},
    )
    logger.debug("Telemetry snapshot: %s", snapshot.model_dump())
    return snapshot
