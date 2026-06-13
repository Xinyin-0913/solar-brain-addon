"""Smart Home Energy homepage tests (product-redesign, no PV required).

Monkeypatches the HA client's get_states so no live Home Assistant is needed.

Run from solar-brain-addon/:  python tests/test_home.py
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["SOLAR_BRAIN_DATA_DIR"] = tempfile.mkdtemp(prefix="solar_brain_home_")
for var in ("SUPERVISOR_TOKEN", "HASSIO_TOKEN", "HOME_ASSISTANT_URL", "HOME_ASSISTANT_TOKEN"):
    os.environ.pop(var, None)

from fastapi.testclient import TestClient  # noqa: E402

from app import database, main  # noqa: E402

# Canned smart-home states: NO PV/solar entities at all.
STATES = [
    {"entity_id": "light.kitchen", "state": "on",
     "attributes": {"friendly_name": "Kitchen Light"}},
    {"entity_id": "switch.tv_plug", "state": "off",
     "attributes": {"friendly_name": "TV Plug"}},
    {"entity_id": "sensor.fridge_power", "state": "120",
     "attributes": {"friendly_name": "Fridge Power",
                    "unit_of_measurement": "W", "device_class": "power"}},
]


async def _fake_get_states():
    return STATES


main.ha_client.get_states = _fake_get_states


def seed_light_samples():
    """~1 h of recent 9 W samples for the kitchen light (today totals > 0)."""
    now = datetime.now(timezone.utc)
    rows = [((now - timedelta(seconds=60 * i)).isoformat(timespec="seconds"),
             "light.kitchen", 9.0, None) for i in range(60)]
    database.insert_device_samples(rows)


def test_homepage_without_pv():
    """Homepage + device API work with zero solar entities mapped."""
    with TestClient(main.app) as client:
        assert client.get("/").status_code == 200
        res = client.get("/api/devices")
        assert res.status_code == 200, res.text
        d = res.json()
        assert d["device_count"] == 3, d           # light, switch, power sensor
        assert d["measured_count"] == 1, d          # fridge power sensor
        assert d["estimated_count"] == 2, d         # light + switch
        # Recommendation endpoint works without PV.
        rec = client.get("/api/home/recommendation")
        assert rec.status_code == 200, rec.text
        assert rec.json()["text"]
    print("PASS homepage works without PV entities")


def test_homepage_uses_device_totals():
    """Seeded device samples flow into the homepage totals."""
    seed_light_samples()
    with TestClient(main.app) as client:
        d = client.get("/api/devices").json()
        assert d["totals_today_kwh"] > 0, d
        assert d["totals_month_kwh"] >= d["totals_today_kwh"], d
        light = next(x for x in d["devices"] if x["entity_id"] == "light.kitchen")
        assert light["mode"] == "estimated" and light["today_kwh"] > 0, light
        assert d["measured_since"] is not None, d
    print("PASS homepage uses smart-home device totals")


def test_solar_section_optional():
    """With no PV roles mapped, mapping is empty and telemetry is unavailable."""
    with TestClient(main.app) as client:
        mapping = client.get("/api/entities/mapping").json()["mappings"]
        pv_roles = {"solar_power", "battery_soc", "grid_import_power",
                    "grid_export_power", "ev_power"}
        assert not (pv_roles & set(mapping)), mapping  # no PV roles -> small card
        # No PV mapped -> telemetry snapshot has every role missing.
        tel = client.get("/api/telemetry/current")
        assert tel.status_code == 200, tel.text
        assert len(tel.json()["missing_roles"]) == 6, tel.json()
    print("PASS solar section is optional when no solar entities mapped")


if __name__ == "__main__":
    test_homepage_without_pv()
    test_homepage_uses_device_totals()
    test_solar_section_optional()
    print("\nALL HOME TESTS PASSED")
