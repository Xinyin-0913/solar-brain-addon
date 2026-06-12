"""Integration test: discovery -> mapping -> normalized telemetry.

Starts the mock HA API as a subprocess, points the app at it, and exercises
the full flow through the real HTTP endpoints.

Run from solar-brain-addon/:  python tests/test_telemetry_integration.py
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ADDON_DIR = Path(__file__).resolve().parent.parent
MOCK_PORT = 8123

# Configure the app BEFORE importing it (config loads at import time).
os.environ["HOME_ASSISTANT_URL"] = f"http://127.0.0.1:{MOCK_PORT}"
os.environ["HOME_ASSISTANT_TOKEN"] = "test-token"
os.environ["SOLAR_BRAIN_DATA_DIR"] = tempfile.mkdtemp(prefix="solar_brain_test_")

sys.path.insert(0, str(ADDON_DIR))


def wait_for_mock(timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(
                f"http://127.0.0.1:{MOCK_PORT}/api/",
                headers={"Authorization": "Bearer test-token"},
                timeout=1.0,
            )
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.3)
    raise RuntimeError("Mock HA did not start in time")


def main() -> None:
    mock = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "tests.mock_ha:app",
         "--port", str(MOCK_PORT), "--log-level", "warning"],
        cwd=ADDON_DIR,
    )
    try:
        wait_for_mock()

        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            # 0. Connection reporting: env-var setup = local mode, manual token.
            res = client.get("/api/status")
            assert res.status_code == 200, res.text
            st = res.json()
            assert st["ha_mode"] == "local" and st["ha_auth"] == "manual_token", st
            assert "local dev token" in st["ha_connection"], st
            assert st["ha_reachable"] is True, st  # mock HA is up
            print("PASS connection mode reporting")

            # 1. Discovery classifies the right entities at the top.
            res = client.get("/api/entities/discover")
            assert res.status_code == 200, res.text
            d = res.json()
            assert d["connection"]["mode"] == "local", d["connection"]
            top = {role: (c[0]["entity_id"] if c else None)
                   for role, c in d["suggestions"].items()}
            assert top["solar_power"] == "sensor.solaredge_pv_power", top
            assert top["battery_soc"] == "sensor.home_battery_soc", top
            assert top["grid_import_power"] == "sensor.grid_import_power", top
            assert top["grid_export_power"] == "sensor.grid_export_power", top
            assert top["ev_power"] == "sensor.wallbox_charging_power", top
            assert top["home_load_power"] == "sensor.house_load_power", top
            # Noise must not appear as candidates.
            all_candidates = [c["entity_id"] for cands in d["suggestions"].values()
                              for c in cands]
            assert "sensor.solar_energy_today" not in all_candidates  # kWh = energy
            assert "sensor.living_room_temperature" not in all_candidates
            # "sensor.water_level" must not match ev_power ("ev" not a token).
            ev_ids = [c["entity_id"] for c in d["suggestions"]["ev_power"]]
            assert "sensor.water_level" not in ev_ids, ev_ids
            print("PASS discovery & classification")

            # 2. Validation: unknown role and unknown entity rejected.
            res = client.post("/api/entities/mapping",
                              json={"mappings": {"warp_core": "sensor.x"}})
            assert res.status_code == 400, res.text
            res = client.post("/api/entities/mapping",
                              json={"mappings": {"solar_power": "sensor.nope"}})
            assert res.status_code == 400, res.text
            print("PASS mapping validation")

            # 3. Save mapping (without home_load -> it must be computed).
            res = client.post("/api/entities/mapping", json={"mappings": {
                "solar_power": "sensor.solaredge_pv_power",
                "battery_soc": "sensor.home_battery_soc",
                "grid_import_power": "sensor.grid_import_power",
                "grid_export_power": "sensor.grid_export_power",
                "ev_power": "sensor.wallbox_charging_power",
            }})
            assert res.status_code == 200, res.text
            assert res.json()["validated"] is True
            res = client.get("/api/entities/mapping")
            assert res.json()["mappings"]["solar_power"] == "sensor.solaredge_pv_power"
            print("PASS mapping save & readback (SQLite)")

            # 4. Telemetry normalization: kW -> W, computed load, unavailable EV.
            res = client.get("/api/telemetry/current")
            assert res.status_code == 200, res.text
            t = res.json()
            assert t["solar_power_w"] == 3200.0, t          # 3.2 kW -> W
            assert t["battery_soc"] == 78.0, t
            assert t["grid_import_w"] == 450.0, t
            assert t["grid_export_w"] == 0.0, t
            assert t["ev_power_w"] is None, t               # "unavailable"
            assert "ev_power" in t["missing_roles"], t
            assert t["home_load_w"] == 3650.0, t            # 3200 + 450 - 0
            assert "home_load_w" in t["estimated_fields"], t
            print("PASS telemetry normalization & computed load")

            # 5. Map a real load sensor -> measured value wins.
            res = client.post("/api/entities/mapping", json={"mappings": {
                "home_load_power": "sensor.house_load_power"}})
            assert res.status_code == 200, res.text
            t = client.get("/api/telemetry/current").json()
            assert t["home_load_w"] == 2750.0, t
            assert t["estimated_fields"] == [], t
            print("PASS measured load overrides computed")

            # 6. Clearing a mapping works.
            res = client.post("/api/entities/mapping",
                              json={"mappings": {"home_load_power": None}})
            assert res.status_code == 200
            assert "home_load_power" not in res.json()["mappings"]
            print("PASS mapping clear")

            # 7. Savings: live rate from real telemetry, summary never guesses.
            res = client.get("/api/savings/current")
            assert res.status_code == 200, res.text
            c = res.json()
            # sc = min(solar 3200 W, computed load 3650 W) = 3200 W
            assert c["self_consumption_w"] == 3200.0, c
            assert c["export_w"] == 0.0, c
            assert abs(c["savings_per_hour_eur"] - 3.2 * 0.30) < 1e-6, c
            assert abs(c["total_benefit_per_hour_eur"] - 0.96) < 1e-6, c
            res = client.get("/api/savings/summary")
            assert res.status_code == 200, res.text
            s = res.json()
            assert s["estimated_annual_savings_eur"] is None, s  # no 24 h history
            assert s["payback"]["progress_percent"] is None, s   # no system cost
            print("PASS savings endpoints")

            # 8. Savings detail endpoint: valid periods, validation, warnings.
            res = client.get("/api/savings/detail?period=today")
            assert res.status_code == 200, res.text
            d = res.json()
            assert d["period"] == "today", d
            assert "formulas" in d and "self_consumption_savings" in d["formulas"], d
            warn_codes = [w["code"] for w in d["warnings"]]
            assert "default_tariff" in warn_codes, warn_codes   # env uses defaults
            assert "no_system_cost" in warn_codes, warn_codes   # no cost configured
            assert client.get("/api/savings/detail?period=lifetime").status_code == 200
            assert client.get("/api/savings/detail?period=year").status_code == 422
            print("PASS savings detail endpoint")

            # 9. Pages render.
            assert client.get("/").status_code == 200
            assert client.get("/settings/entities").status_code == 200
            assert client.get("/savings").status_code == 200
            print("PASS pages render")

        print("\nALL TESTS PASSED")
    finally:
        mock.terminate()


if __name__ == "__main__":
    main()
