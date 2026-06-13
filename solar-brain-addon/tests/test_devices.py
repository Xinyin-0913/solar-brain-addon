"""Unit tests for Smart Home Energy (per-device usage).

Run from solar-brain-addon/:  python tests/test_devices.py
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["SOLAR_BRAIN_DATA_DIR"] = tempfile.mkdtemp(prefix="solar_brain_devices_")

from app import database, devices  # noqa: E402
from app.models import AddonConfig  # noqa: E402

CFG = AddonConfig(electricity_import_price_eur_per_kwh=0.30,
                  default_wattage_light=9.0,
                  default_wattage_smart_plug=1.0,
                  default_wattage_motion_sensor=0.1)

BASE = datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)


def state(entity_id, value, unit="", device_class="", name=None):
    return {
        "entity_id": entity_id,
        "state": str(value),
        "attributes": {
            "friendly_name": name or entity_id,
            "unit_of_measurement": unit,
            "device_class": device_class,
        },
    }


def approx(a, b, eps=1e-4):
    return abs(a - b) < eps


def test_classification():
    cases = [
        (state("light.kitchen", "on"), "light", "estimated", 9.0),
        (state("switch.tv_plug", "on"), "switch", "estimated", 1.0),
        (state("binary_sensor.hall_motion", "off", device_class="motion"),
         "motion", "estimated", 0.1),
        (state("sensor.fridge_power", "120", unit="W", device_class="power"),
         "power_sensor", "measured", None),
        (state("sensor.house_energy", "3500", unit="kWh", device_class="energy"),
         "energy_sensor", "measured", None),
        (state("sensor.sensor_battery", "55", unit="%", device_class="battery"),
         "battery", "none", None),
    ]
    for st, dtype, mode, watt in cases:
        d = devices.classify_device(st, CFG)
        assert d is not None, st["entity_id"]
        assert d["device_type"] == dtype, (st["entity_id"], d)
        assert d["mode"] == mode, (st["entity_id"], d)
        assert d["estimated_wattage"] == watt, (st["entity_id"], d)
    # Irrelevant entities are skipped.
    assert devices.classify_device(state("sensor.temp", "21", unit="°C"), CFG) is None
    assert devices.classify_device(state("automation.x", "on"), CFG) is None
    print("PASS device classification")


def test_current_power():
    light = devices.classify_device(state("light.k", "on"), CFG)
    assert devices.current_power_w(light, state("light.k", "on")) == 9.0
    assert devices.current_power_w(light, state("light.k", "off")) == 0.0
    # Measured power sensor, kW normalized to W.
    ps = devices.classify_device(state("sensor.p", "1.5", unit="kW"), CFG)
    assert devices.current_power_w(ps, state("sensor.p", "1.5", unit="kW")) == 1500.0
    # Energy sensor has no instantaneous power.
    es = devices.classify_device(state("sensor.e", "10", unit="kWh"), CFG)
    assert devices.current_power_w(es, state("sensor.e", "10", unit="kWh")) is None
    # Motion sensor always draws its small constant.
    m = devices.classify_device(state("binary_sensor.m", "off", device_class="motion"), CFG)
    assert devices.current_power_w(m, state("binary_sensor.m", "off", device_class="motion")) == 0.1
    # Unavailable -> None.
    assert devices.current_power_w(light, state("light.k", "unavailable")) is None
    print("PASS current power (estimated, measured, energy, motion, unavailable)")


def _samples(power_w, count, step_s=60):
    """Power samples at fixed cadence starting at BASE."""
    return [{"ts": (BASE + timedelta(seconds=i*step_s)).isoformat(),
             "entity_id": "x", "power_w": power_w, "energy_kwh": None}
            for i in range(count)]


def test_estimated_device_energy_and_cost():
    """A 9 W light on for exactly 1 h -> 0.009 kWh -> 0.0027 EUR."""
    light = devices.classify_device(state("light.k", "on"), CFG)
    samples = _samples(9.0, 61)  # 60 intervals x 60 s = 1 h at 9 W
    usage = devices.compute_device_usage(
        light, state("light.k", "on"), samples, samples, 0.30)
    assert approx(usage.today_kwh, 0.009), usage
    assert approx(usage.today_cost_eur, 0.0027), usage
    assert usage.mode == "estimated" and usage.current_power_w == 9.0
    assert usage.month_kwh == usage.today_kwh
    print("PASS estimated device energy & cost")


def test_measured_power_sensor_energy():
    """A 120 W fridge sampled for 2 h -> 0.24 kWh -> 0.072 EUR."""
    ps = devices.classify_device(state("sensor.fridge", "120", unit="W"), CFG)
    samples = _samples(120.0, 121)  # 120 intervals x 60 s = 2 h
    usage = devices.compute_device_usage(
        ps, state("sensor.fridge", "120", unit="W"), samples, samples, 0.30)
    assert approx(usage.today_kwh, 0.24), usage
    assert approx(usage.today_cost_eur, 0.072), usage
    assert usage.mode == "measured" and usage.current_power_w == 120.0
    print("PASS measured power-sensor energy & cost")


def test_measured_energy_sensor_cumulative():
    """Cumulative kWh meter: today = current - first reading in window."""
    es = devices.classify_device(state("sensor.house", "3500", unit="kWh"), CFG)
    samples = [
        {"ts": BASE.isoformat(), "entity_id": "x", "power_w": None, "energy_kwh": 3500.0},
        {"ts": (BASE+timedelta(hours=1)).isoformat(), "entity_id": "x",
         "power_w": None, "energy_kwh": 3502.5},
    ]
    live = state("sensor.house", "3504.0", unit="kWh")  # current reading now
    usage = devices.compute_device_usage(es, live, samples, samples, 0.30)
    assert approx(usage.today_kwh, 4.0), usage          # 3504.0 - 3500.0
    assert approx(usage.today_cost_eur, 1.2), usage     # 4.0 * 0.30
    # Meter reset (current < first) must not produce negative usage.
    reset = devices.compute_device_usage(
        es, state("sensor.house", "10", unit="kWh"), samples, samples, 0.30)
    assert reset.today_kwh == 0.0, reset
    print("PASS measured energy-sensor cumulative differencing")


def test_battery_has_no_cost():
    batt = devices.classify_device(
        state("sensor.motion_battery", "80", unit="%", device_class="battery"), CFG)
    usage = devices.compute_device_usage(
        batt, state("sensor.motion_battery", "80", unit="%"), [], [], 0.30)
    assert usage.device_type == "battery" and usage.mode == "none"
    assert usage.today_cost_eur == 0.0 and usage.month_cost_eur == 0.0
    assert usage.today_kwh == 0.0
    assert "battery" in usage.note.lower()
    print("PASS battery device has no grid cost")


def test_gap_capping_in_device_integration():
    """A long gap between two samples only credits 300 s of energy."""
    light = devices.classify_device(state("light.k", "on"), CFG)
    samples = [
        {"ts": BASE.isoformat(), "entity_id": "x", "power_w": 9.0, "energy_kwh": None},
        {"ts": (BASE+timedelta(hours=5)).isoformat(), "entity_id": "x",
         "power_w": 9.0, "energy_kwh": None},
    ]
    usage = devices.compute_device_usage(
        light, state("light.k", "on"), samples, samples, 0.30)
    assert approx(usage.today_kwh, 9.0 * 300 / 3.6e6), usage  # only 300 s credited
    print("PASS gap capping in device integration")


def test_discover_and_db_roundtrip():
    """discover_devices + sample persistence works without any PV mapping."""
    database.init_db()
    states = [
        state("light.kitchen", "on"),
        state("switch.tv", "off"),
        state("sensor.fridge_power", "150", unit="W", device_class="power"),
        state("sensor.temp", "21", unit="°C"),  # ignored
    ]
    found = devices.discover_devices(states, CFG)
    assert {d["entity_id"] for d in found} == {
        "light.kitchen", "switch.tv", "sensor.fridge_power"}, found
    # Persist a sample per device and read it back.
    ts = BASE.isoformat()
    rows = []
    for d in found:
        s = next(x for x in states if x["entity_id"] == d["entity_id"])
        p, e = devices.make_sample(d, s)
        rows.append((ts, d["entity_id"], p, e))
    database.insert_device_samples(rows)
    back = database.get_device_samples_since(None)
    assert len(back) == 3, back
    assert database.get_first_device_sample_ts() == ts
    print("PASS discover + DB roundtrip (no PV mapping needed)")


if __name__ == "__main__":
    test_classification()
    test_current_power()
    test_estimated_device_energy_and_cost()
    test_measured_power_sensor_energy()
    test_measured_energy_sensor_cumulative()
    test_battery_has_no_cost()
    test_gap_capping_in_device_integration()
    test_discover_and_db_roundtrip()
    print("\nALL DEVICE TESTS PASSED")
