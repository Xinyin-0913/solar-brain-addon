# Solar Brain (Home Assistant Add-on)

Smart solar energy advisor for Home Assistant. MVP version: exposes a web
dashboard and a REST API on port **8099** with placeholder recommendation
logic (no hardware control yet).

## Features

- Web dashboard at `http://<host>:8099/` with live telemetry
- **Energy entity mapping** at `/settings/entities`: auto-discovers and
  classifies your solar / battery / grid / EV sensors, with manual override
  (see [docs/entity_mapping.md](../docs/entity_mapping.md))
- Unified telemetry: `GET /api/telemetry/current` — normalized snapshot
  (watts everywhere, SOC in %), one flaky sensor never breaks it
- Telemetry history persisted to SQLite every 60 s
- **Savings Engine**: `GET /api/savings/current` and `GET /api/savings/summary`
  — today/week/month/lifetime savings, annual estimate, and payback progress,
  all derived from measured telemetry and your tariff
  (formulas: [docs/savings_engine.md](../docs/savings_engine.md))
- **Savings explainability**: `/savings` page with period selector, the
  formulas shown next to every number, and transparency warnings (low data
  coverage, default tariff, missing system cost); API:
  `GET /api/savings/detail?period=today|week|month|lifetime`
- **Smart Home Energy**: `/devices` page and `GET /api/devices` show
  per-device electricity usage and cost (lights, switches, power/energy
  sensors, batteries) - works with or without a PV system. Measured devices
  use real sensors; estimated devices use configurable default wattages
  (`default_wattage_light`, `default_wattage_smart_plug`,
  `default_wattage_motion_sensor`)
- `GET /api/status` — add-on status, time, location, current recommendation
- `GET /api/recommendation` — recommendation with action, risk level, reason
- `GET /api/entities/discover` / `GET|POST /api/entities/mapping`
- `GET /health` — liveness check (used by the Supervisor watchdog)
- Live weather via the free [Open-Meteo](https://open-meteo.com/) API when a
  location is configured; safe stub data otherwise

## Recommendation logic (placeholder)

Rules in priority order:

| Condition | Action | Risk |
|---|---|---|
| Wind speed > 40 km/h | `enable_safe_mode` | high |
| Solar forecast < 2 kWh | `save_battery` | medium |
| Hour between 10:00 and 15:00 | `use_solar_energy` | low |
| Otherwise | `monitor` | low |

## Two ways to run it

| | Home Assistant add-on | Local development |
|---|---|---|
| HA connection | **Zero config** — automatic via Supervisor | `HOME_ASSISTANT_URL` + `HOME_ASSISTANT_TOKEN` env vars |
| Token needed | **No** | Yes, long-lived access token (debugging only) |
| Startup log | `Runtime: mode=addon auth=supervisor_token` | `Runtime: mode=local auth=manual_token \| not_configured` |
| UI shows | "Connected via Home Assistant Supervisor." | "Home Assistant connection requires local dev token." |

## Installation in Home Assistant

1. Copy the `solar-brain-addon` folder to the `/addons` directory of your
   Home Assistant installation (e.g. via the Samba or SSH add-on):

   ```
   /addons/solar-brain-addon/
   ```

2. In Home Assistant go to **Settings → Add-ons → Add-on Store**, open the
   menu (⋮ top right) and click **Check for updates** (or reload the page).

3. **Solar Brain** appears under **Local add-ons**. Open it and click
   **Install** (the Supervisor builds the Docker image locally — this takes
   a few minutes).

4. On the **Configuration** tab set your options (all optional):

   > **No token or URL required.** As an add-on, Solar Brain connects to the
   > Home Assistant API automatically through the Supervisor
   > (`homeassistant_api: true`). The UI shows
   > *"Connected via Home Assistant Supervisor."*

   | Option | Description |
   |---|---|
   | `latitude` / `longitude` | Your location, enables live weather. `0/0` = stub data. |
   | `electricity_import_price_eur_per_kwh` | Your grid tariff — used by the savings engine. |
   | `feed_in_tariff_eur_per_kwh` | Your feed-in rate — used by the savings engine. |
   | `system_cost_eur` | PV system investment; enables payback tracking. `0` = off. |
   | `installation_date` | `YYYY-MM-DD`, shown for context in savings. |
   | `openrouter_api_key` | Reserved for future AI features. |
   | `enable_ai` | Reserved for future AI features. Keep `false`. |

5. Click **Start**, then **Open Web UI** (or browse to
   `http://homeassistant.local:8099`).

## Running locally (without Home Assistant)

Local dev mode is detected automatically (no `SUPERVISOR_TOKEN` present);
the startup log prints `Runtime: mode=local ...` and the UI shows
*"Home Assistant connection requires local dev token."*

A token is **only needed for debugging against a real HA instance**: set
`HOME_ASSISTANT_URL` and `HOME_ASSISTANT_TOKEN` (a long-lived access token
from your HA profile page) as environment variables. Without them the app
still runs — telemetry endpoints return 503 with guidance, everything else
works.

With docker compose:

```bash
cd solar-brain-addon
docker compose up --build
```

Or with plain docker:

```bash
cd solar-brain-addon
docker build -t solar-brain .
docker run --rm -p 8099:8099 -e LATITUDE=52.52 -e LONGITUDE=13.40 solar-brain
```

Or directly with Python 3.12:

```bash
cd solar-brain-addon
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8099
```

Then open <http://localhost:8099>.

## API examples

```bash
curl http://localhost:8099/api/status
```

```json
{
  "addon_status": "running",
  "current_time": "2026-06-12T12:30:00",
  "location": "52.5200, 13.4000",
  "solar_recommendation": "Peak solar window. Use solar energy now."
}
```

```bash
curl http://localhost:8099/api/recommendation
```

```json
{
  "recommendation_text": "Peak solar window. Use solar energy now.",
  "suggested_action": "use_solar_energy",
  "risk_level": "low",
  "reason": "Current hour (12:00) is inside the solar window (10:00-15:00)."
}
```

## Troubleshooting: entities do not load

Work through these in order:

1. **Is the add-on actually connected?** Check the dashboard's Status card
   (or `GET /api/status`). As an add-on it should say
   *"Connected via Home Assistant Supervisor."* — if it says HA is
   temporarily unavailable, Home Assistant is restarting; it reconnects
   automatically within a minute.
2. **Check the startup log** (add-on → Log tab). The line
   `Runtime: mode=... auth=...` tells you exactly how Solar Brain is
   connecting. `auth=not_configured` in local mode means the env vars are
   missing.
3. **No suggestions on the mapping page?** Discovery only proposes
   `sensor.*` entities with unit `W`, `kW`, or `%`. Verify your inverter /
   battery integration is installed and its sensors exist under
   **Developer Tools → States** in Home Assistant.
4. **A sensor exists but isn't suggested?** Generic names (e.g.
   `sensor.power_meter`) match no role keywords — pick it manually from
   "All compatible sensors" in the dropdown.
5. **Telemetry shows `—` for one value?** That sensor is currently
   `unavailable` in HA. Solar Brain skips it (listed in `missing_roles` of
   `/api/telemetry/current`) and heals automatically on the next 60 s poll.
6. Full mapping guide: [docs/entity_mapping.md](../docs/entity_mapping.md).

## Project structure

```
solar-brain-addon/
  config.yaml          # Home Assistant add-on manifest
  build.yaml           # Base image per architecture
  Dockerfile
  run.sh               # Container entrypoint
  docker-compose.yml   # Local development
  requirements.txt
  app/
    main.py              # FastAPI app, routes, background telemetry poller
    ui.py                # Dashboard + entity mapping pages (inline HTML)
    solar_logic.py       # Placeholder recommendation rules
    entity_discovery.py  # Auto-classification of HA entities per role
    telemetry.py         # Normalized TelemetrySnapshot builder
    database.py          # SQLite (mappings + telemetry history)
    weather_client.py    # Open-Meteo client with stub fallback
    ha_client.py         # HA REST API client
    models.py            # Pydantic models + config loading
  tests/
    mock_ha.py           # Mock Home Assistant REST API
    test_telemetry_integration.py
```

After starting the add-on, open **Entity mapping** from the dashboard footer
(`/settings/entities`) to connect your real sensors — full guide in
[docs/entity_mapping.md](../docs/entity_mapping.md).

## Roadmap (not in MVP)

- AI-generated recommendations via OpenRouter (`enable_ai`)
- Reading real PV/battery sensors from Home Assistant
- Hardware control (inverter / battery modes)
