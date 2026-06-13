"""Smart Home Energy - per-device electricity usage and cost.

The primary product: works with or without a PV system, entirely independent
of the solar/PV entity mapping. Two calculation modes per device:

- **measured**: a power sensor (W/kW), a cumulative energy sensor (kWh), or a
  controllable device that reports power in its attributes (e.g. a smart plug
  with ``current_power_w``). Real readings are used.
- **estimated**: lights/switches/motion with no power reading - usage is
  wattage x on-duration. Wattage comes from the device profile's
  ``rated_power_w`` if set, otherwise the default for the device type.

A device profile may also disable estimation (``estimation_enabled=False``),
making the device **monitoring** only (on/off visible, no cost claimed).

Energy is accumulated from samples the poller stores every cycle (same
gap-capped integration as the savings engine). Nothing is extrapolated -
missing time counts as zero, and totals only cover the period since the
add-on started collecting data.
"""

import logging
import re
from datetime import datetime, timedelta, timezone

from .models import AddonConfig, DeviceProfile, DeviceUsage, HomeRecommendation

logger = logging.getLogger("solar_brain.devices")

GAP_CAP_SECONDS = 300.0
WS_PER_KWH = 3_600_000.0

POWER_UNITS = {"w", "kw"}
ENERGY_UNITS = {"wh", "kwh"}
ON_STATES = {"on", "open", "home", "playing", "true"}
UNAVAILABLE = {"unavailable", "unknown", "none", ""}

# Tokens that mark a sensor as ENERGY GENERATION / feed-in, not home
# consumption. Such sensors must never be counted as consuming devices,
# never claim cost, and never trigger a "high consumption" recommendation.
GENERATION_KEYWORDS = {
    "solar", "pv", "photovoltaic", "generation", "generated",
    "production", "produced", "inverter", "yield", "export",
}


def _is_generation_sensor(entity_id: str, name: str) -> bool:
    """True if a sensor's id/name marks it as generation/feed-in."""
    tokens = {t for t in re.split(r"[^a-z0-9]+", f"{entity_id} {name}".lower()) if t}
    return bool(tokens & GENERATION_KEYWORDS)

# Attribute keys some integrations use to report live power on a switch/light.
POWER_ATTR_KEYS = ("current_power_w", "power_w", "power")

# High consumption / long-on thresholds for the home recommendation.
HIGH_POWER_W = 2000.0
LONG_ON_HOURS = 6.0

BATTERY_NOTE = "battery powered - no grid cost"
ESTIMATED_NOTE = "estimated from wattage x on-time"
MONITORING_NOTE = "estimation disabled - monitoring only"


def _to_watts(value: float, unit: str) -> float:
    return value * 1000.0 if unit == "kw" else value


def _to_kwh(value: float, unit: str) -> float:
    return value / 1000.0 if unit == "wh" else value


def _power_attribute(attrs: dict) -> float | None:
    """A numeric power-in-watts value from device attributes, or None."""
    for key in POWER_ATTR_KEYS:
        if key in attrs:
            try:
                return max(float(attrs[key]), 0.0)
            except (ValueError, TypeError):
                continue
    return None


def classify_device(
    state: dict, config: AddonConfig, profile: DeviceProfile | None = None,
    excluded_ids: set[str] | None = None,
) -> dict | None:
    """Classify one HA state into a trackable CONSUMING device, or None to skip.

    Returns a dict carrying everything later steps need: entity_id, name
    (display_name override applied), device_type, appliance_type, mode,
    estimated_wattage, unit, and power_attr (the attribute key when a
    controllable device reports power).

    Entities in ``excluded_ids`` (those mapped to the optional solar/PV
    module) and obvious generation sensors are never treated as consumption.
    """
    entity_id = state.get("entity_id", "")
    if "." not in entity_id:
        return None
    if excluded_ids and entity_id in excluded_ids:
        return None  # belongs to the solar/PV module, not the device list
    domain = entity_id.split(".", 1)[0]
    attrs = state.get("attributes", {})
    name = (profile.display_name if profile and profile.display_name
            else attrs.get("friendly_name", entity_id))
    unit = str(attrs.get("unit_of_measurement", "")).lower()
    device_class = str(attrs.get("device_class", "")).lower()

    def make(device_type, mode, wattage=None, appliance=None, power_attr=None):
        return {
            "entity_id": entity_id, "name": name, "device_type": device_type,
            "appliance_type": (profile.appliance_type if profile else None) or appliance,
            "mode": mode, "estimated_wattage": wattage, "unit": unit,
            "power_attr": power_attr,
        }

    if domain in ("light", "switch"):
        default_w = (config.default_wattage_light if domain == "light"
                     else config.default_wattage_smart_plug)
        appliance = "light" if domain == "light" else "smart_plug"
        # 1. Measured wins: the device itself reports power in its attributes.
        if _power_attribute(attrs) is not None:
            return make(domain, "measured", appliance=appliance,
                        power_attr=next(k for k in POWER_ATTR_KEYS if k in attrs))
        # 2. Profile may disable estimation -> monitoring only.
        if profile and not profile.estimation_enabled:
            return make(domain, "monitoring", appliance=appliance)
        # 3. Profile rated power overrides the type default.
        wattage = (profile.rated_power_w if profile and profile.rated_power_w
                   else default_w)
        return make(domain, "estimated", wattage=wattage, appliance=appliance)

    if domain == "binary_sensor" and device_class == "motion":
        return make("motion", "estimated", wattage=config.default_wattage_motion_sensor,
                    appliance="motion")

    if domain == "sensor":
        if device_class == "battery" or (unit == "%" and "batt" in entity_id.lower()):
            return make("battery", "none", appliance="battery")
        # Generation / feed-in sensors are not consumption - skip entirely.
        if (unit in POWER_UNITS or unit in ENERGY_UNITS) and _is_generation_sensor(
            entity_id, attrs.get("friendly_name", "")
        ):
            return None
        if unit in POWER_UNITS and device_class in ("power", ""):
            return make("power_sensor", "measured", appliance="power_sensor")
        if unit in ENERGY_UNITS:
            return make("energy_sensor", "measured", appliance="energy_sensor")
    return None


def discover_devices(
    states: list[dict], config: AddonConfig,
    profiles: dict[str, DeviceProfile] | None = None,
    excluded_ids: set[str] | None = None,
) -> list[dict]:
    """All classifiable CONSUMING devices from HA states, profiles applied."""
    profiles = profiles or {}
    devices = []
    for s in states:
        d = classify_device(s, config, profiles.get(s.get("entity_id", "")), excluded_ids)
        if d is not None:
            devices.append(d)
    by_type: dict[str, int] = {}
    for d in devices:
        by_type[d["device_type"]] = by_type.get(d["device_type"], 0) + 1
    logger.info("Device discovery: %d devices %s", len(devices), by_type)
    return devices


def current_power_w(device: dict, state: dict) -> float | None:
    """Live power draw for a device, or None if not derivable right now."""
    raw = str(state.get("state", "")).strip().lower()
    if raw in UNAVAILABLE:
        return None

    dtype, mode = device["device_type"], device["mode"]
    if mode == "monitoring":
        return None
    if mode == "measured":
        if dtype == "energy_sensor":
            return None
        if device.get("power_attr"):  # controllable device reporting power
            return _power_attribute(state.get("attributes", {}))
        try:
            return max(_to_watts(float(state["state"]), device["unit"]), 0.0)
        except (ValueError, KeyError):
            return None
    if dtype == "battery":
        return 0.0
    if dtype == "motion":
        return device["estimated_wattage"]  # sensor is always powered
    return device["estimated_wattage"] if raw in ON_STATES else 0.0


def make_sample(device: dict, state: dict) -> tuple[float | None, float | None]:
    """(power_w, energy_kwh) to persist this cycle for a device."""
    if device["device_type"] == "energy_sensor":
        try:
            return None, _to_kwh(float(state["state"]), device["unit"])
        except (ValueError, KeyError):
            return None, None
    return current_power_w(device, state), None


def _integrate_power_kwh(samples: list[dict]) -> float:
    """Left-rectangle integration of power_w samples (gap-capped) -> kWh."""
    ws = 0.0
    for cur, nxt in zip(samples, samples[1:]):
        try:
            dt = (datetime.fromisoformat(nxt["ts"]) - datetime.fromisoformat(cur["ts"])).total_seconds()
        except (ValueError, TypeError):
            continue
        if dt <= 0:
            continue
        power = cur.get("power_w")
        if power is None:
            continue
        ws += max(power, 0.0) * min(dt, GAP_CAP_SECONDS)
    return ws / WS_PER_KWH


def _cumulative_kwh(samples: list[dict], current_value: float | None) -> float:
    """Energy in window = last reading - first reading (clamped >= 0)."""
    values = [s["energy_kwh"] for s in samples if s.get("energy_kwh") is not None]
    if not values:
        return 0.0
    last = current_value if current_value is not None else values[-1]
    return max(last - values[0], 0.0)


def _period_starts_utc(now_utc: datetime) -> tuple[str, str]:
    """(today_start, month_start) as UTC ISO, from local calendar boundaries."""
    local = now_utc.astimezone()
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    month = midnight.replace(day=1)
    return (
        midnight.astimezone(timezone.utc).isoformat(timespec="seconds"),
        month.astimezone(timezone.utc).isoformat(timespec="seconds"),
    )


def compute_device_usage(
    device: dict,
    state: dict | None,
    samples_today: list[dict],
    samples_month: list[dict],
    import_price: float,
) -> DeviceUsage:
    """Build the table row for one device from its samples + live state."""
    dtype, mode = device["device_type"], device["mode"]
    cost_bearing = mode in ("measured", "estimated")
    cur_power = current_power_w(device, state) if state is not None else None

    if dtype == "energy_sensor":
        live_kwh = None
        if state is not None:
            try:
                live_kwh = _to_kwh(float(state["state"]), device["unit"])
            except (ValueError, KeyError, TypeError):
                live_kwh = None
        today_kwh = _cumulative_kwh(samples_today, live_kwh)
        month_kwh = _cumulative_kwh(samples_month, live_kwh)
    elif cost_bearing:
        today_kwh = _integrate_power_kwh(samples_today)
        month_kwh = _integrate_power_kwh(samples_month)
    else:
        today_kwh = month_kwh = 0.0

    if dtype == "battery":
        note = BATTERY_NOTE
    elif mode == "monitoring":
        note = MONITORING_NOTE
    elif mode == "estimated":
        note = ESTIMATED_NOTE
    else:
        note = ""

    return DeviceUsage(
        entity_id=device["entity_id"],
        name=device["name"],
        device_type=dtype,
        appliance_type=device.get("appliance_type"),
        mode=mode,
        estimated_wattage=device.get("estimated_wattage"),
        current_power_w=cur_power,
        today_kwh=round(today_kwh, 4),
        month_kwh=round(month_kwh, 4),
        today_cost_eur=round(today_kwh * import_price, 4) if cost_bearing else 0.0,
        month_cost_eur=round(month_kwh * import_price, 4) if cost_bearing else 0.0,
        note=note,
    )


def is_profilable(device: dict) -> bool:
    """Controllable devices (lights/switches) accept a user profile."""
    return device["device_type"] in ("light", "switch")


def _hours_on(state: dict) -> float | None:
    """Hours since last_changed if the entity is currently on, else None."""
    if str(state.get("state", "")).strip().lower() not in ON_STATES:
        return None
    last = state.get("last_changed") or state.get("last_updated")
    if not last:
        return None
    try:
        changed = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max((datetime.now(timezone.utc) - changed).total_seconds() / 3600.0, 0.0)


def compute_home_recommendation(
    states: list[dict], config: AddonConfig,
    profiles: dict[str, DeviceProfile] | None = None,
    excluded_ids: set[str] | None = None,
) -> HomeRecommendation:
    """Honest smart-home recommendation from real consuming devices only.

    Generation/feed-in sensors and solar/PV-mapped entities are excluded, so
    they never produce a false "high consumption" alert.
    """
    profiles = profiles or {}
    devices = discover_devices(states, config, profiles, excluded_ids)
    states_by_id = {s.get("entity_id"): s for s in states}

    if not devices:
        return HomeRecommendation(
            text="No devices discovered yet.",
            detail="Add lights, switches, or power sensors in Home Assistant, "
                   "then they appear here automatically.",
            severity="info", action_url="settings/entities",
        )

    estimated = [d for d in devices if d["mode"] == "estimated"]
    measured = [d for d in devices if d["mode"] == "measured"]

    # 1. High consumption right now (most actionable).
    high = None
    for d in devices:
        p = current_power_w(d, states_by_id.get(d["entity_id"], {}))
        if p is not None and p >= HIGH_POWER_W and (high is None or p > high[1]):
            high = (d["name"], p)
    if high:
        return HomeRecommendation(
            text=f"High consumption: {high[0]} is drawing {high[1]/1000:.2f} kW.",
            detail="Check whether this device needs to be running right now.",
            severity="warning",
        )

    # 2. A controllable device left on for a long time.
    longest = None
    for d in devices:
        if d["device_type"] in ("light", "switch"):
            h = _hours_on(states_by_id.get(d["entity_id"], {}))
            if h is not None and h >= LONG_ON_HOURS and (longest is None or h > longest[1]):
                longest = (d["name"], h)
    if longest:
        return HomeRecommendation(
            text=f"{longest[0]} has been on for {longest[1]:.0f} hours.",
            detail="If that is unexpected, consider turning it off.",
            severity="info",
        )

    # 3. Accuracy nudge: mostly estimated devices.
    if estimated and len(estimated) >= max(len(measured), 1):
        return HomeRecommendation(
            text="Most devices are estimated.",
            detail="Set device profiles (rated power) for smart plugs and lights "
                   "to make cost estimates more accurate.",
            severity="info", action_url="settings/devices",
        )

    # 4. All clear.
    return HomeRecommendation(
        text="No high consumption detected.",
        detail="Your devices look normal right now.",
        severity="info",
    )
