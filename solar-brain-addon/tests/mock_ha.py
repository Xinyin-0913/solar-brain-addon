"""Minimal mock of the Home Assistant REST API for integration testing.

Run: uvicorn tests.mock_ha:app --port 8123
Requires Authorization: Bearer test-token (mimics HA auth).
"""

from fastapi import FastAPI, Header, HTTPException

app = FastAPI()

TOKEN = "test-token"

STATES = [
    {
        "entity_id": "sensor.solaredge_pv_power",
        "state": "3.2",
        "attributes": {
            "friendly_name": "SolarEdge PV Power",
            "unit_of_measurement": "kW",
            "device_class": "power",
        },
    },
    {
        "entity_id": "sensor.home_battery_soc",
        "state": "78",
        "attributes": {
            "friendly_name": "Home Battery SOC",
            "unit_of_measurement": "%",
            "device_class": "battery",
        },
    },
    {
        "entity_id": "sensor.grid_import_power",
        "state": "450",
        "attributes": {
            "friendly_name": "Grid Import Power",
            "unit_of_measurement": "W",
            "device_class": "power",
        },
    },
    {
        "entity_id": "sensor.grid_export_power",
        "state": "0",
        "attributes": {
            "friendly_name": "Grid Export Power",
            "unit_of_measurement": "W",
            "device_class": "power",
        },
    },
    {
        "entity_id": "sensor.wallbox_charging_power",
        "state": "unavailable",
        "attributes": {
            "friendly_name": "Wallbox Charging Power",
            "unit_of_measurement": "W",
            "device_class": "power",
        },
    },
    {
        "entity_id": "sensor.house_load_power",
        "state": "2750",
        "attributes": {
            "friendly_name": "House Load Power",
            "unit_of_measurement": "W",
            "device_class": "power",
        },
    },
    # Noise that discovery must NOT misclassify:
    {
        "entity_id": "sensor.living_room_temperature",
        "state": "21.5",
        "attributes": {
            "friendly_name": "Living Room Temperature",
            "unit_of_measurement": "°C",
            "device_class": "temperature",
        },
    },
    {
        "entity_id": "sensor.solar_energy_today",
        "state": "12.4",
        "attributes": {
            "friendly_name": "Solar Energy Today",
            "unit_of_measurement": "kWh",
            "device_class": "energy",
        },
    },
    {
        "entity_id": "sensor.phone_battery_level",
        "state": "55",
        "attributes": {
            "friendly_name": "Phone Battery Level",
            "unit_of_measurement": "%",
            "device_class": "battery",
        },
    },
    {
        "entity_id": "sensor.water_level",
        "state": "800",
        "attributes": {
            "friendly_name": "Water Level Pump Power",
            "unit_of_measurement": "W",
            "device_class": "power",
        },
    },
    {
        "entity_id": "switch.pool_pump",
        "state": "off",
        "attributes": {"friendly_name": "Pool Pump"},
    },
    {
        "entity_id": "light.living_room",
        "state": "on",
        "attributes": {"friendly_name": "Living Room Light"},
    },
    {
        "entity_id": "switch.coffee_maker",
        "state": "off",
        "attributes": {"friendly_name": "Coffee Maker"},
    },
    {
        "entity_id": "switch.kasa_tv_plug",
        "state": "on",
        # Reports its own power -> classified as measured, not estimated.
        "attributes": {"friendly_name": "TV (Kasa plug)", "current_power_w": 95.0},
    },
]


def _check_auth(authorization: str | None) -> None:
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/api/")
async def api_root(authorization: str | None = Header(default=None)) -> dict:
    _check_auth(authorization)
    return {"message": "API running."}


@app.get("/api/states")
async def api_states(authorization: str | None = Header(default=None)) -> list:
    _check_auth(authorization)
    return STATES


@app.get("/api/states/{entity_id}")
async def api_state(entity_id: str, authorization: str | None = Header(default=None)) -> dict:
    _check_auth(authorization)
    for state in STATES:
        if state["entity_id"] == entity_id:
            return state
    raise HTTPException(status_code=404, detail="Entity not found")
