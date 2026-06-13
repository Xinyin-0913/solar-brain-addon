"""Smart Home Energy - per-device electricity usage and cost.

Works with or without a PV system; entirely independent of the PV/solar
entity mapping. Two calculation modes per device:

- **measured**: the device has a power sensor (W/kW) or a cumulative energy
  sensor (kWh) - real readings are used.
- **estimated**: lights/switches/motion sensors with no power sensor - usage
  is configured_wattage x on-duration.

Energy is accumulated from samples the background poller stores every cycle
(same gap-capped integration the savings engine uses), so today/month totals
reflect what Solar Brain actually measured since it started running. Nothing
is extrapolated - missing time counts as zero.
"""

import logging
from datetime import datetime, timedelta, timezone

from .models import AddonConfig, DeviceUsage

logger = logging.getLogger("solar_brain.devices")

GAP_CAP_SECONDS = 300.0
WS_PER_KWH = 3_600_000.0

POWER_UNITS = {"w", "kw"}
ENERGY_UNITS = {"wh", "kwh"}
ON_STATES = {"on", "open", "home", "playing", "true"}

BATTERY_NOTE = "battery powered - no grid cost"
ESTIMATED_NOTE = "estimated from default wattage x on-time"


def _to_watts(value: float, unit: str) -> float:
    return value * 1000.0 if unit == "kw" else value


def _to_kwh(value: float, unit: str) -> float:
    return value / 1000.0 if unit == "wh" else value


def classify_device(state: dict, config: AddonConfig) -> dict | None:
    """Classify one HA state into a trackable device, or None to skip.

    Returns a dict: entity_id, name, device_type, mode, estimated_wattage,
    unit (for sensors). Cost-bearing types: light, switch, power_sensor,
    energy_sensor, motion. battery -> mode "none" (no grid cost).
    """
    entity_id = state.get("entity_id", "")
    if "." not in entity_id:
        return None
    domain = entity_id.split(".", 1)[0]
    attrs = state.get("attributes", {})
    name = attrs.get("friendly_name", entity_id)
    unit = str(attrs.get("unit_of_measurement", "")).lower()
    device_class = str(attrs.get("device_class", "")).lower()

    def make(device_type, mode, wattage=None):
        return {
            "entity_id": entity_id, "name": name, "device_type": device_type,
            "mode": mode, "estimated_wattage": wattage, "unit": unit,
        }

    if domain == "light":
        return make("light", "estimated", config.default_wattage_light)
    if domain == "switch":
        return make("switch", "estimated", config.default_wattage_smart_plug)
    if domain == "binary_sensor" and device_class == "motion":
        return make("motion", "estimated", config.default_wattage_motion_sensor)
    if domain == "sensor":
        if device_class == "battery" or (unit == "%" and "batt" in entity_id.lower()):
            return make("battery", "none")
        if unit in POWER_UNITS and device_class in ("power", ""):
            return make("power_sensor", "measured")
        if unit in ENERGY_UNITS:
            return make("energy_sensor", "measured")
    return None


def discover_devices(states: list[dict], config: AddonConfig) -> list[dict]:
    """All classifiable devices from HA states."""
    devices = [d for s in states if (d := classify_device(s, config)) is not None]
    by_type: dict[str, int] = {}
    for d in devices:
        by_type[d["device_type"]] = by_type.get(d["device_type"], 0) + 1
    logger.info("Device discovery: %d devices %s", len(devices), by_type)
    return devices


def current_power_w(device: dict, state: dict) -> float | None:
    """Live power draw for a device, or None if not derivable right now.

    - power_sensor: the sensor's W value (kW normalized).
    - energy_sensor: None (cumulative; no instantaneous power).
    - battery: 0 (no grid draw).
    - estimated light/switch: wattage when on, else 0.
    - estimated motion sensor: always its small constant draw.
    """
    raw = str(state.get("state", "")).strip().lower()
    if raw in ("unavailable", "unknown", "none", ""):
        return None

    dtype, mode = device["device_type"], device["mode"]
    if mode == "measured":
        if dtype == "energy_sensor":
            return None
        try:
            return max(_to_watts(float(state["state"]), device["unit"]), 0.0)
        except (ValueError, KeyError):
            return None
    if dtype == "battery":
        return 0.0
    if dtype == "motion":
        return device["estimated_wattage"]  # sensor is always powered
    # light / switch: only when on
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
    """Energy used in window = last reading - first reading (clamped >= 0).

    A meter reset (last < first) yields 0 rather than a negative number.
    """
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
    dtype = device["device_type"]
    cost_bearing = dtype != "battery"
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

    note = ""
    if dtype == "battery":
        note = BATTERY_NOTE
    elif device["mode"] == "estimated":
        note = ESTIMATED_NOTE

    return DeviceUsage(
        entity_id=device["entity_id"],
        name=device["name"],
        device_type=dtype,
        mode=device["mode"],
        estimated_wattage=device.get("estimated_wattage"),
        current_power_w=cur_power,
        today_kwh=round(today_kwh, 4),
        month_kwh=round(month_kwh, 4),
        today_cost_eur=round(today_kwh * import_price, 4) if cost_bearing else 0.0,
        month_cost_eur=round(month_kwh * import_price, 4) if cost_bearing else 0.0,
        note=note,
    )
