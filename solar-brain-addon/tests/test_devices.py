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
from app.models import AddonConfig, DeviceProfile  # noqa: E402

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


def test_unmapped_generation_sensor_excluded():
    """Obvious generation/feed-in sensors are never consuming devices."""
    generation = [
        state("sensor.solaredge_pv_power", "3200", unit="W", device_class="power"),
        state("sensor.solar_production", "2.5", unit="kW", device_class="power"),
        state("sensor.pv_generation_today", "12", unit="kWh", device_class="energy"),
        state("sensor.inverter_power", "500", unit="W", device_class="power"),
        state("sensor.grid_export_power", "100", unit="W", device_class="power"),
    ]
    for st in generation:
        assert devices.classify_device(st, CFG) is None, st["entity_id"]
    # Real consumption sensors are still kept.
    assert devices.classify_device(
        state("sensor.fridge_power", "120", unit="W", device_class="power"), CFG
    )["device_type"] == "power_sensor"
    assert devices.classify_device(
        state("sensor.grid_import_power", "450", unit="W", device_class="power"), CFG
    )["device_type"] == "power_sensor"
    # A battery named "solar ..." stays a (no-cost) battery, not excluded.
    batt = devices.classify_device(
        state("sensor.solar_battery_level", "80", unit="%", device_class="battery"), CFG)
    assert batt["device_type"] == "battery", batt
    print("PASS unmapped generation sensor excluded from consumption")


def test_mapped_pv_entity_excluded():
    """An entity mapped to the solar/PV module is excluded from the device list."""
    excluded = {"sensor.house_main_power"}
    st = state("sensor.house_main_power", "3000", unit="W", device_class="power")
    assert devices.classify_device(st, CFG, None, excluded) is None
    # discover_devices drops it but keeps a normal device.
    found = devices.discover_devices(
        [st, state("light.kitchen", "on")], CFG, {}, excluded)
    assert {d["entity_id"] for d in found} == {"light.kitchen"}, found
    print("PASS mapped PV entity excluded from top devices")


def test_recommendation_ignores_generation():
    """High generation must not raise a false 'high consumption' alert."""
    # 5 kW solar generation + only small consuming devices.
    states = [
        state("sensor.solaredge_pv_power", "5000", unit="W", device_class="power"),
        state("light.kitchen", "on"),
        state("switch.tv_plug", "off"),
    ]
    rec = devices.compute_home_recommendation(states, CFG)
    assert rec.severity != "warning", rec           # no false high-consumption
    assert "high consumption" not in rec.text.lower(), rec
    assert "solaredge" not in rec.text.lower() and "pv" not in rec.text.lower(), rec

    # A mapped high-power entity is likewise ignored by the recommendation.
    states2 = [
        state("sensor.house_main_power", "6000", unit="W", device_class="power"),
        state("light.kitchen", "on"),
    ]
    rec2 = devices.compute_home_recommendation(
        states2, CFG, {}, {"sensor.house_main_power"})
    assert "high consumption" not in rec2.text.lower(), rec2

    # But a REAL consuming device above the threshold still triggers the alert.
    states3 = [
        state("sensor.oven_power", "3000", unit="W", device_class="power"),
        state("light.kitchen", "on"),
    ]
    rec3 = devices.compute_home_recommendation(states3, CFG)
    assert rec3.severity == "warning" and "high consumption" in rec3.text.lower(), rec3
    print("PASS recommendation based only on real consuming devices")


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


def test_profile_rated_power_overrides_default():
    """A device profile's rated_power_w overrides the type default wattage."""
    st = state("switch.heater", "on")
    profile = DeviceProfile(entity_id="switch.heater", appliance_type="heater",
                            rated_power_w=2000.0)
    d = devices.classify_device(st, CFG, profile)
    assert d["mode"] == "estimated", d
    assert d["estimated_wattage"] == 2000.0, d        # not the 1 W default
    assert d["appliance_type"] == "heater", d
    assert devices.current_power_w(d, st) == 2000.0
    # No profile -> falls back to the default switch wattage.
    d2 = devices.classify_device(st, CFG, None)
    assert d2["estimated_wattage"] == 1.0, d2
    print("PASS device profile rated_power_w overrides default wattage")


def test_measured_takes_priority_over_profile():
    """A device reporting power (attribute) is measured even if a profile exists."""
    st = state("switch.kasa_plug", "on")
    st["attributes"]["current_power_w"] = 42.5     # plug reports real power
    profile = DeviceProfile(entity_id="switch.kasa_plug", rated_power_w=2000.0)
    d = devices.classify_device(st, CFG, profile)
    assert d["mode"] == "measured", d              # measured wins over profile
    assert d["power_attr"] == "current_power_w", d
    assert devices.current_power_w(d, st) == 42.5  # uses reading, not 2000 W
    print("PASS measured mode takes priority over estimated profile")


def test_display_name_and_estimation_disabled():
    """display_name override applies; estimation_enabled=False -> monitoring."""
    st = state("switch.toilet_plug", "on", name="IKEA smart plug")
    profile = DeviceProfile(entity_id="switch.toilet_plug",
                            display_name="IKEA smart plug - toilet",
                            rated_power_w=15.0, estimation_enabled=False)
    d = devices.classify_device(st, CFG, profile)
    assert d["name"] == "IKEA smart plug - toilet", d
    assert d["mode"] == "monitoring", d
    usage = devices.compute_device_usage(d, st, [], [], 0.30)
    assert usage.current_power_w is None and usage.today_cost_eur == 0.0, usage
    assert "monitoring" in usage.note.lower()
    print("PASS display_name override + estimation disabled (monitoring)")


if __name__ == "__main__":
    test_classification()
    test_current_power()
    test_profile_rated_power_overrides_default()
    test_measured_takes_priority_over_profile()
    test_display_name_and_estimation_disabled()
    test_unmapped_generation_sensor_excluded()
    test_mapped_pv_entity_excluded()
    test_recommendation_ignores_generation()
    test_estimated_device_energy_and_cost()
    test_measured_power_sensor_energy()
    test_measured_energy_sensor_cumulative()
    test_battery_has_no_cost()
    test_gap_capping_in_device_integration()
    test_discover_and_db_roundtrip()
    print("\nALL DEVICE TESTS PASSED")
