# Changelog

## 0.5.1

**Build fix — installable on real Home Assistant.**

- The Supervisor builds add-ons from Home Assistant's Alpine base images
  (which ship no Python), so `pip3: not found` broke the install. The
  Dockerfile now installs `python3` + `py3-pip` via `apk` and works
  regardless of which base image the Supervisor passes.
- `build.yaml` pins the official HA base images
  (`ghcr.io/home-assistant/{amd64,aarch64}-base:3.21`, Alpine 3.21 =
  Python 3.12).
- Dropped `armv7`: our dependency `pydantic-core` publishes no armv7 musl
  wheels, so the build cannot succeed there. Supported: amd64, aarch64
  (Home Assistant Green, Yellow, RPi 4/5 64-bit).

## 0.5.0

**Fully Home Assistant native.**

- As an add-on, Solar Brain now connects to the HA API automatically via
  the Supervisor — **no token, no URL, zero configuration**. The
  `home_assistant_url` / `home_assistant_token` add-on options were
  removed; legacy values left in existing installs are ignored safely.
- Manual URL/token remain available **for local development only**, via
  the `HOME_ASSISTANT_URL` / `HOME_ASSISTANT_TOKEN` environment variables.
- Startup log states the runtime clearly:
  `Runtime: mode=addon|local auth=supervisor_token|manual_token|not_configured`.
- `GET /api/status` now reports `ha_mode`, `ha_auth`, `ha_reachable`, and a
  user-facing connection message; during an HA restart the add-on shows
  "Home Assistant is temporarily unavailable. Solar Brain will reconnect
  automatically."
- README split into add-on (zero config) vs. local development usage, plus
  a troubleshooting section for entity loading.

## 0.4.0

- Savings Explainability: `/savings` page with period selector
  (today/week/month/lifetime), every number shown with its formula, and
  transparency warnings (low data coverage, default tariff, missing system
  cost, payback unavailable). New `GET /api/savings/detail?period=...`.

## 0.3.0

- Savings Engine V1: all euros derived from measured telemetry history ×
  configured tariff. New options: `electricity_import_price_eur_per_kwh`,
  `feed_in_tariff_eur_per_kwh`, `system_cost_eur`, `installation_date`.
  New endpoints `GET /api/savings/current` and `GET /api/savings/summary`;
  savings cards on the dashboard. Gap-capped energy integration (max 5 min
  credited per gap); projections refuse to extrapolate from < 24 h of data.

## 0.2.0

- Energy Dashboard integration: automatic discovery and classification of
  solar / battery SOC / grid import / grid export / EV sensors; entity
  mapping page at `/settings/entities`; mappings stored in SQLite; unified
  `GET /api/telemetry/current` (normalized to watts); background telemetry
  poller (60 s) persisting history.

## 0.1.0

- Initial MVP: FastAPI dashboard on port 8099, `GET /api/status`,
  `GET /api/recommendation`, placeholder rule engine, Open-Meteo weather
  with stub fallback, optional HA REST client.
