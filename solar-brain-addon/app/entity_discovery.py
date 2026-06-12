"""Automatic discovery and classification of Home Assistant entities.

Heuristic scoring, not magic: an entity is a candidate for a role when its
unit fits (W/kW for power roles, % for SOC) and at least one role keyword
matches its entity_id or friendly name. Keyword matching is token-based so
"ev" matches "sensor.ev_charger" but not "sensor.water_level".

The user always confirms or overrides on /settings/entities - discovery only
produces ranked suggestions.
"""

import logging
import re

logger = logging.getLogger("solar_brain.discovery")

POWER_UNITS = {"w", "kw"}
PERCENT_UNITS = {"%"}

# role -> matching rules. Keyword weight reflects how unambiguous the word is.
ROLE_RULES: dict[str, dict] = {
    "solar_power": {
        "units": POWER_UNITS,
        "device_class": "power",
        "keywords": {"solar": 3, "pv": 3, "photovoltaic": 3, "production": 1,
                     "generation": 1, "inverter": 1},
    },
    "battery_soc": {
        "units": PERCENT_UNITS,
        "device_class": "battery",
        "keywords": {"soc": 3, "state_of_charge": 3, "battery": 2, "charge": 1},
    },
    "grid_import_power": {
        "units": POWER_UNITS,
        "device_class": "power",
        "keywords": {"import": 3, "from_grid": 3, "grid": 2, "demand": 1,
                     "consumption": 1},
    },
    "grid_export_power": {
        "units": POWER_UNITS,
        "device_class": "power",
        "keywords": {"export": 3, "to_grid": 3, "feed_in": 3, "feed": 2,
                     "return": 2, "grid": 1},
    },
    "ev_power": {
        "units": POWER_UNITS,
        "device_class": "power",
        "keywords": {"ev": 3, "wallbox": 3, "charger": 2, "car": 2,
                     "vehicle": 2, "charging": 1},
    },
    "home_load_power": {
        "units": POWER_UNITS,
        "device_class": "power",
        "keywords": {"load": 3, "house": 2, "home": 2, "consumption": 2,
                     "usage": 1},
    },
}

DEVICE_CLASS_BONUS = 2
MAX_SUGGESTIONS = 8


def _tokens(state: dict) -> set[str]:
    haystack = f"{state.get('entity_id', '')} {state.get('attributes', {}).get('friendly_name', '')}"
    return {t for t in re.split(r"[^a-z0-9]+", haystack.lower()) if t}


def _keyword_score(keywords: dict[str, int], tokens: set[str]) -> int:
    score = 0
    for keyword, weight in keywords.items():
        # Multi-word keywords ("state_of_charge") require all their tokens.
        if all(part in tokens for part in keyword.split("_")):
            score += weight
    return score


def _summarize(state: dict, score: int) -> dict:
    attrs = state.get("attributes", {})
    return {
        "entity_id": state.get("entity_id", ""),
        "name": attrs.get("friendly_name", state.get("entity_id", "")),
        "unit": attrs.get("unit_of_measurement", ""),
        "device_class": attrs.get("device_class", ""),
        "state": state.get("state", ""),
        "score": score,
    }


def classify_entities(states: list[dict]) -> dict[str, list[dict]]:
    """Return ranked candidate entities per telemetry role."""
    suggestions: dict[str, list[dict]] = {role: [] for role in ROLE_RULES}

    for state in states:
        entity_id = state.get("entity_id", "")
        if not entity_id.startswith("sensor."):
            continue
        attrs = state.get("attributes", {})
        unit = str(attrs.get("unit_of_measurement", "")).lower()
        device_class = str(attrs.get("device_class", "")).lower()
        tokens = _tokens(state)

        for role, rules in ROLE_RULES.items():
            if unit not in rules["units"]:
                continue
            score = _keyword_score(rules["keywords"], tokens)
            if score <= 0:
                continue  # unit alone is not evidence
            if device_class == rules["device_class"]:
                score += DEVICE_CLASS_BONUS
            suggestions[role].append(_summarize(state, score))

    for role in suggestions:
        suggestions[role].sort(key=lambda c: c["score"], reverse=True)
        suggestions[role] = suggestions[role][:MAX_SUGGESTIONS]

    found = {role: len(items) for role, items in suggestions.items()}
    logger.info("Entity discovery: candidates per role %s", found)
    return suggestions


def list_mappable_sensors(states: list[dict]) -> list[dict]:
    """All sensors with a unit usable for any role (for manual selection)."""
    usable_units = POWER_UNITS | PERCENT_UNITS
    sensors = [
        _summarize(state, 0)
        for state in states
        if state.get("entity_id", "").startswith("sensor.")
        and str(state.get("attributes", {}).get("unit_of_measurement", "")).lower()
        in usable_units
    ]
    sensors.sort(key=lambda s: s["entity_id"])
    return sensors
