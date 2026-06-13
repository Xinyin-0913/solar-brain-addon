"""Solar Brain - Home Assistant add-on.

FastAPI app exposing a dashboard, entity mapping page, and REST API on
port 8099. Telemetry is polled from Home Assistant in the background and
persisted to SQLite.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

from . import database, devices, entity_discovery, models, savings, telemetry, ui
from .ha_client import HomeAssistantClient
from .models import (
    TELEMETRY_ROLES,
    AddonConfig,
    DeviceProfilesUpdate,
    DevicesResponse,
    HomeRecommendation,
    MappingUpdate,
    Recommendation,
    SavingsCurrent,
    SavingsDetail,
    SavingsSummary,
    StatusResponse,
    TelemetrySnapshot,
)
from .solar_logic import get_recommendation
from .weather_client import get_weather

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("solar_brain")

config = AddonConfig.load()
ha_client = HomeAssistantClient(config)

TELEMETRY_POLL_SECONDS = 60

if ha_client.mode == "addon":
    HA_UNAVAILABLE_DETAIL = (
        "Home Assistant API is not reachable via the Supervisor. This is "
        "usually temporary (Home Assistant restarting) - it reconnects "
        "automatically."
    )
else:
    HA_UNAVAILABLE_DETAIL = (
        "Home Assistant connection requires local dev token. Set the "
        "HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN environment variables "
        "(long-lived access token) for local development. When installed as "
        "a Home Assistant add-on, no configuration is needed."
    )


DEVICE_SAMPLE_RETENTION_DAYS = 40


async def _poll_telemetry_loop() -> None:
    """Every cycle: sample devices, and snapshot PV telemetry if mapped.

    States are fetched once and shared. Device sampling runs even when no PV
    entities are mapped, so the Smart Home Energy view works without a PV
    system.
    """
    while True:
        await asyncio.sleep(TELEMETRY_POLL_SECONDS)
        try:
            if not ha_client.is_configured:
                continue
            states = await ha_client.get_states()
            if states is None:
                continue

            _sample_devices(states)

            if database.get_mappings():
                snapshot = await telemetry.build_snapshot(ha_client, states=states)
                if snapshot is not None:
                    database.insert_snapshot(snapshot)
        except Exception:
            logger.exception("Telemetry poll failed")


def _sample_devices(states: list[dict]) -> None:
    """Persist one power/energy sample per discovered device; prune old rows."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    profiles = database.get_device_profiles()
    excluded = set(database.get_mappings().values())  # solar/PV module entities
    rows: list[tuple[str, str, float | None, float | None]] = []
    for state in states:
        device = devices.classify_device(
            state, config, profiles.get(state.get("entity_id", "")), excluded
        )
        if device is None:
            continue
        power_w, energy_kwh = devices.make_sample(device, state)
        rows.append((ts, device["entity_id"], power_w, energy_kwh))
    database.insert_device_samples(rows)

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=DEVICE_SAMPLE_RETENTION_DAYS)
    ).isoformat(timespec="seconds")
    database.prune_device_samples(cutoff)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    await ha_client.log_startup_diagnostics()
    logger.info(
        "Runtime: mode=%s auth=%s (%s)",
        ha_client.mode, ha_client.auth, ha_client.connection_message,
    )
    poller = asyncio.create_task(_poll_telemetry_loop())
    logger.info(
        "Solar Brain started (location=%s, ai=%s, poll=%ss)",
        f"{config.latitude},{config.longitude}" if config.has_location else "not set",
        "enabled" if config.enable_ai else "disabled",
        TELEMETRY_POLL_SECONDS,
    )
    yield
    poller.cancel()


app = FastAPI(title="Smart Home Energy", version="0.7.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("Unhandled error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/health")
async def health() -> dict:
    """Liveness check used by the Supervisor watchdog."""
    return {"status": "ok"}


@app.get("/api/debug/runtime")
async def api_debug_runtime() -> dict:
    """Safe runtime diagnostics: how HA access resolved. No secret values."""
    diag = ha_client.safe_runtime_diagnostics()
    diag["reachable"] = await ha_client.ping()
    return diag


# --- Pages -----------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return ui.DASHBOARD_HTML


@app.get("/settings/entities", response_class=HTMLResponse)
async def settings_entities() -> str:
    return ui.SETTINGS_HTML


@app.get("/savings", response_class=HTMLResponse)
async def savings_page() -> str:
    return ui.SAVINGS_HTML


@app.get("/devices", response_class=HTMLResponse)
async def devices_page() -> str:
    return ui.DEVICES_HTML


@app.get("/settings/devices", response_class=HTMLResponse)
async def device_profiles_page() -> str:
    return ui.DEVICE_PROFILES_HTML


# --- Entity discovery & mapping ---------------------------------------------


async def _require_states() -> list[dict]:
    states = await ha_client.get_states()
    if states is None:
        raise HTTPException(status_code=503, detail=HA_UNAVAILABLE_DETAIL)
    return states


@app.get("/api/entities/discover")
async def api_discover_entities() -> dict:
    """Classified entity suggestions per role, plus all mappable sensors."""
    states = await _require_states()
    return {
        "suggestions": entity_discovery.classify_entities(states),
        "sensors": entity_discovery.list_mappable_sensors(states),
        "current_mapping": database.get_mappings(),
        "connection": {
            "mode": ha_client.mode,
            "auth": ha_client.auth,
            "message": ha_client.connection_message,
        },
    }


@app.get("/api/entities/mapping")
async def api_get_mapping() -> dict:
    return {"mappings": database.get_mappings()}


@app.post("/api/entities/mapping")
async def api_save_mapping(update: MappingUpdate) -> dict:
    unknown_roles = [r for r in update.mappings if r not in TELEMETRY_ROLES]
    if unknown_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown roles: {unknown_roles}. Valid roles: {TELEMETRY_ROLES}",
        )

    # Validate entity ids against HA when reachable; otherwise save with a warning.
    validated = False
    states = await ha_client.get_states()
    if states is not None:
        known_ids = {s.get("entity_id") for s in states}
        bad = [e for e in update.mappings.values() if e and e not in known_ids]
        if bad:
            raise HTTPException(
                status_code=400,
                detail=f"Entities not found in Home Assistant: {bad}",
            )
        validated = True
    else:
        logger.warning("Saving mapping without validation (HA unreachable)")

    saved = database.save_mappings(
        update.mappings, datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    return {"mappings": saved, "validated": validated}


# --- Smart home energy (primary) --------------------------------------------


@app.get("/api/home/recommendation", response_model=HomeRecommendation)
async def api_home_recommendation() -> HomeRecommendation:
    """Honest smart-home recommendation from live device data."""
    states = await ha_client.get_states()
    if states is None:
        raise HTTPException(status_code=503, detail=HA_UNAVAILABLE_DETAIL)
    return devices.compute_home_recommendation(
        states, config, database.get_device_profiles(),
        set(database.get_mappings().values()),
    )


@app.get("/api/devices/profiles")
async def api_get_device_profiles() -> dict:
    """Saved profiles + the controllable devices that can take one."""
    profiles = database.get_device_profiles()
    controllable: list[dict] = []
    states = await ha_client.get_states()
    if states is not None:
        for state in states:
            device = devices.classify_device(
                state, config, profiles.get(state.get("entity_id", ""))
            )
            if device is not None and devices.is_profilable(device):
                controllable.append({
                    "entity_id": device["entity_id"],
                    "name": device["name"],
                    "device_type": device["device_type"],
                    "appliance_type": device.get("appliance_type"),
                    "mode": device["mode"],
                    "estimated_wattage": device.get("estimated_wattage"),
                })
        controllable.sort(key=lambda d: d["entity_id"])
    return {
        "appliance_types": models.APPLIANCE_TYPES,
        "profiles": {eid: p.model_dump() for eid, p in profiles.items()},
        "controllable_devices": controllable,
    }


@app.post("/api/devices/profiles")
async def api_save_device_profiles(update: DeviceProfilesUpdate) -> dict:
    """Upsert device profiles. A rated_power_w of null clears the override."""
    invalid = [p.appliance_type for p in update.profiles
               if p.appliance_type not in models.APPLIANCE_TYPES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown appliance_type(s): {invalid}. "
                   f"Valid: {models.APPLIANCE_TYPES}",
        )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for profile in update.profiles:
        database.save_device_profile(profile, now)
    return {"saved": len(update.profiles),
            "profiles": {eid: p.model_dump()
                         for eid, p in database.get_device_profiles().items()}}


# --- Telemetry ---------------------------------------------------------------


@app.get("/api/devices", response_model=DevicesResponse)
async def api_devices() -> DevicesResponse:
    """Per-device electricity usage and cost (works without a PV system)."""
    states = await ha_client.get_states()
    if states is None:
        raise HTTPException(status_code=503, detail=HA_UNAVAILABLE_DETAIL)

    now = datetime.now(timezone.utc)
    today_start, month_start = devices._period_starts_utc(now)
    states_by_id = {s.get("entity_id"): s for s in states}
    profiles = database.get_device_profiles()
    excluded = set(database.get_mappings().values())  # solar/PV module entities
    discovered = devices.discover_devices(states, config, profiles, excluded)

    # One DB read for the whole month; split per device / per today in memory.
    month_rows = database.get_device_samples_since(month_start)
    by_entity: dict[str, list[dict]] = {}
    for row in month_rows:
        by_entity.setdefault(row["entity_id"], []).append(row)

    price = config.electricity_import_price_eur_per_kwh
    usages = []
    for device in discovered:
        eid = device["entity_id"]
        month_samples = by_entity.get(eid, [])
        today_samples = [r for r in month_samples if r["ts"] >= today_start]
        usages.append(
            devices.compute_device_usage(
                device, states_by_id.get(eid), today_samples, month_samples, price
            )
        )

    usages.sort(key=lambda u: u.month_cost_eur, reverse=True)
    return DevicesResponse(
        timestamp=now.isoformat(timespec="seconds"),
        import_price_eur_per_kwh=price,
        device_count=len(usages),
        measured_count=sum(1 for u in usages if u.mode == "measured"),
        estimated_count=sum(1 for u in usages if u.mode == "estimated"),
        devices=usages,
        totals_today_kwh=round(sum(u.today_kwh for u in usages), 3),
        totals_month_kwh=round(sum(u.month_kwh for u in usages), 3),
        totals_today_cost_eur=round(sum(u.today_cost_eur for u in usages), 2),
        totals_month_cost_eur=round(sum(u.month_cost_eur for u in usages), 2),
        totals_current_power_w=round(
            sum(u.current_power_w or 0.0 for u in usages), 1
        ),
        measured_since=database.get_first_device_sample_ts(),
    )


@app.get("/api/telemetry/current", response_model=TelemetrySnapshot)
async def api_telemetry_current() -> TelemetrySnapshot:
    """Normalized live telemetry snapshot (watts everywhere, SOC in %)."""
    snapshot = await telemetry.build_snapshot(ha_client)
    if snapshot is None:
        raise HTTPException(status_code=503, detail=HA_UNAVAILABLE_DETAIL)
    return snapshot


# --- Savings -----------------------------------------------------------------


@app.get("/api/savings/current", response_model=SavingsCurrent)
async def api_savings_current() -> SavingsCurrent:
    """Instantaneous savings rates from live telemetry."""
    snapshot = await telemetry.build_snapshot(ha_client)
    if snapshot is None:
        raise HTTPException(status_code=503, detail=HA_UNAVAILABLE_DETAIL)
    return savings.current_savings(snapshot, config)


@app.get("/api/savings/summary", response_model=SavingsSummary)
async def api_savings_summary() -> SavingsSummary:
    """Aggregated savings (today/week/month/lifetime) from stored history."""
    return savings.compute_summary(config)


@app.get("/api/savings/detail", response_model=SavingsDetail)
async def api_savings_detail(
    period: str = Query("today", pattern="^(today|week|month|lifetime)$"),
) -> SavingsDetail:
    """Explainable savings for one period: energy, money, coverage, warnings."""
    return savings.compute_detail(config, period)


# --- Status & recommendations ------------------------------------------------


@app.get("/api/status", response_model=StatusResponse)
async def api_status() -> StatusResponse:
    reachable = await ha_client.ping()
    weather = await get_weather(config)
    recommendation = get_recommendation(weather)
    location = (
        f"{config.latitude:.4f}, {config.longitude:.4f}"
        if config.has_location
        else "not configured"
    )
    return StatusResponse(
        addon_status="running",
        current_time=datetime.now().isoformat(timespec="seconds"),
        location=location,
        solar_recommendation=recommendation.recommendation_text,
        ha_mode=ha_client.mode,
        ha_auth=ha_client.auth,
        ha_connection=ha_client.status_message(reachable),
        ha_reachable=reachable,
    )


@app.get("/api/recommendation", response_model=Recommendation)
async def api_recommendation() -> Recommendation:
    weather = await get_weather(config)
    return get_recommendation(weather)
