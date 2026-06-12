# Entity Mapping — How Solar Brain Reads Your Energy Data

Solar Brain does not talk to your inverter, battery, or wallbox directly.
It reads the **Home Assistant entities** your existing integrations already
provide (SolarEdge, Fronius, Victron, Huawei, Shelly, ESPHome, …) and
normalizes them into one unified telemetry model. You tell it once which
sensor plays which role — that's the entity mapping.

## The roles

| Role | What it is | Required unit | Required? |
|---|---|---|---|
| `solar_power` | Current PV output | W or kW | Recommended |
| `battery_soc` | Battery state of charge | % | Recommended |
| `grid_import_power` | Power drawn from the grid right now | W or kW | Recommended |
| `grid_export_power` | Power fed into the grid right now | W or kW | Recommended |
| `ev_power` | Wallbox / EV charger power | W or kW | Optional |
| `home_load_power` | Total house consumption | W or kW | Optional — computed when unmapped |

Nothing is strictly required: unmapped roles simply produce `null` in the
telemetry (listed under `missing_roles`). The more you map, the better the
recommendations get.

## Setting it up

1. Open the Solar Brain dashboard and click **Entity mapping**
   (or browse to `/settings/entities`).
2. Solar Brain fetches all entities from Home Assistant and shows **ranked
   suggestions** per role. Each dropdown also contains every other
   compatible sensor under "All compatible sensors".
3. Click **Auto-fill suggestions** to accept the top suggestion for every
   empty role, adjust anything that's wrong, then **Save mapping**.
4. Check the **Live telemetry** card on the dashboard — values should
   appear within seconds.

Mappings are stored in SQLite (`/data/solar_brain.db`), so they survive
add-on restarts and updates.

## How auto-discovery works (and why it sometimes gets it wrong)

Discovery is heuristic, not magic:

- Only `sensor.*` entities are considered.
- The **unit must fit**: W/kW for power roles, % for battery SOC. This is
  why energy sensors (kWh) never show up — they measure totals, not power.
- Role **keywords** are matched against the entity id and friendly name
  (token-based, so `ev` matches `sensor.ev_charger` but not
  `sensor.water_level`). Examples: `solar`/`pv` for solar, `soc`/
  `state_of_charge` for battery, `export`/`feed_in` for grid export,
  `wallbox`/`charger` for EV.
- A matching `device_class` (`power`, `battery`) adds to the score.

Suggestions are ranked by score, the top 8 per role are shown. **You always
have the final say** — discovery never maps anything by itself.

Typical gotchas:

- **Generic names** like `sensor.power_meter` won't be suggested anywhere —
  pick them manually from "All compatible sensors".
- **One sensor suggested for both grid import and export**: many meters
  expose a single signed `grid_power` sensor (positive = import,
  negative = export). Map it to *import* for now; proper signed-sensor
  support is on the roadmap.
- **Phone/device batteries** can appear as SOC suggestions (they're `%` +
  `battery`). Your home battery usually ranks higher; double-check anyway.

## The unified telemetry model

`GET /api/telemetry/current` returns:

```json
{
  "timestamp": "2026-06-12T11:48:45+00:00",
  "solar_power_w": 3200.0,
  "battery_soc": 78.0,
  "grid_import_w": 450.0,
  "grid_export_w": 0.0,
  "home_load_w": 3650.0,
  "ev_power_w": null,
  "missing_roles": ["ev_power"],
  "estimated_fields": ["home_load_w"]
}
```

Normalization rules:

- All power values are converted to **watts** (kW sensors × 1000).
- Battery SOC is clamped to 0–100 %.
- `unavailable` / `unknown` / non-numeric states become `null` and the role
  is listed in `missing_roles` — one flaky sensor never breaks the snapshot.
- If no `home_load_power` sensor is mapped, home load is **computed** as
  `solar + grid_import − grid_export` and flagged in `estimated_fields`.
  Note: this estimate ignores battery charge/discharge flows, so it is
  rough while the battery is working. Map a real load sensor if you have one.
- Returns **503** when Home Assistant itself is unreachable (with a hint
  about configuring URL/token).

A background poller persists a snapshot to SQLite every 60 seconds (only
when at least one role is mapped) — this history feeds the upcoming charts
and savings reports.

## API reference

| Endpoint | Description |
|---|---|
| `GET /api/entities/discover` | Ranked suggestions per role + all mappable sensors + current mapping |
| `GET /api/entities/mapping` | Current role → entity mapping |
| `POST /api/entities/mapping` | Save mapping: `{"mappings": {"solar_power": "sensor.x", "ev_power": null}}` — `null` clears a role |
| `GET /api/telemetry/current` | Normalized live snapshot (see above) |

`POST /api/entities/mapping` validates that roles are known and that the
entity ids exist in Home Assistant (rejected with 400 otherwise). If HA is
temporarily unreachable, the mapping is saved unvalidated and the response
contains `"validated": false`.

## Troubleshooting

- **"Home Assistant API is not reachable"** — when running as an add-on
  this should never happen (the Supervisor token is used automatically);
  standalone, set `HOME_ASSISTANT_URL` and `HOME_ASSISTANT_TOKEN`
  (a long-lived access token from your HA profile page).
- **A role shows `—` on the dashboard** — check `missing_roles` in
  `/api/telemetry/current`, then check the sensor's state in HA
  (Developer Tools → States). Unavailable sensors heal automatically on the
  next poll.
- **Wrong suggestion ranked first** — just pick the right one manually;
  suggestions are only suggestions.
