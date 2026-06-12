# Savings Engine V1 — Every Formula, Documented

**Contract:** every euro Solar Brain displays is derived from measured
telemetry snapshots and the user's configured tariffs. No interpolation
across outages, no backfill, no guesses — when there isn't enough data,
the API returns `null`, never an invented number.

Implementation: `app/savings.py` · Tests: `tests/test_savings.py`
(keep this document in sync with both).

---

## 1. Inputs

### Telemetry (measured)

Snapshots persisted to SQLite every 60 s by the background poller
(`telemetry_snapshots` table): `solar_power_w`, `home_load_w`,
`grid_import_w`, `grid_export_w`, `battery_soc`, each possibly `null`
when a sensor was unavailable. Note: `home_load_w` may itself be computed
(`solar + import − export`) when no load sensor is mapped — see
`docs/entity_mapping.md`.

### User settings (add-on options)

| Option | Meaning | Default |
|---|---|---|
| `electricity_import_price_eur_per_kwh` | What 1 kWh from the grid costs you | 0.30 |
| `feed_in_tariff_eur_per_kwh` | What 1 kWh exported earns you | 0.08 |
| `system_cost_eur` | Total PV system investment (for payback) | 0 = off |
| `installation_date` | YYYY-MM-DD, informational | "" |

## 2. Instantaneous values — `GET /api/savings/current`

From a live telemetry snapshot:

```
self_consumption_w   = max(min(solar_power_w, home_load_w), 0)
export_w             = max(grid_export_w, 0)

savings_per_hour_eur           = self_consumption_w / 1000 × import_price
export_earnings_per_hour_eur   = export_w / 1000 × feed_in_tariff
total_benefit_per_hour_eur     = savings_per_hour_eur + export_earnings_per_hour_eur
```

Rationale: every watt of solar you consume yourself is a watt you did not
buy at the import price; every watt exported earns the feed-in tariff.
If `solar_power_w` or `home_load_w` is unavailable, the dependent fields
are `null` (an export-only total is still returned when only export is known).

Negative readings (signed sensors, inverter standby draw) are clamped to 0 —
savings are never negative in V1.

## 3. Energy integration (the core)

Power snapshots are integrated into energy with **left-rectangle
integration, gap-capped**:

```
For each consecutive snapshot pair (tᵢ, tᵢ₊₁):
    dt = min(tᵢ₊₁ − tᵢ, 300 s)
    E_self_consumption += max(min(solarᵢ, loadᵢ), 0) × dt
    E_export           += max(exportᵢ, 0) × dt
    E_solar            += max(solarᵢ, 0) × dt
kWh = Ws / 3,600,000
```

Properties worth knowing:

- **Gap rule:** if snapshots are more than 300 s apart (add-on was off,
  HA restarted), only the first 300 s are credited at the last-known power.
  A 30-hour outage therefore contributes at most 5 minutes of energy —
  savings are *undercounted* during outages, by design. The
  `data_coverage_hours` field in every period makes this visible.
- **Missing values:** a snapshot with `home_load_w = null` contributes no
  self-consumption for its interval (solar production is still counted if
  known). Missing data always lowers the result, never raises it.
- **Accuracy:** at 60 s sampling, left-rectangle vs. exact integration
  differs by well under 1 % for residential load profiles.
- The interval from the newest snapshot to "now" is not counted
  (max 60 s of lag).

## 4. Period money — `GET /api/savings/summary`

For each period, over the snapshots in that period:

```
self_consumption_savings_eur = E_self_consumption_kwh × import_price
export_earnings_eur          = E_export_kwh × feed_in_tariff
total_benefit_eur            = self_consumption_savings_eur + export_earnings_eur
```

Period boundaries (host-local time, converted to UTC for queries):

| Period | Start |
|---|---|
| `today` | local midnight |
| `this_week` | local midnight last Monday |
| `this_month` | local midnight on the 1st |
| `lifetime` | first stored snapshot (**measured data only — no backfill** to `installation_date`) |

Prices are applied at computation time: if you change your tariff, all
displayed history is revalued at the new tariff. (Tariff-change history is
a V2 concern; documented limitation for now.)

## 5. Projections

```
observed_days                = (now − first_snapshot_ts) / 86,400 s
average_daily_benefit_eur    = lifetime.total_benefit_eur / observed_days
estimated_annual_savings_eur = average_daily_benefit_eur × 365
```

**Refusal rule:** with less than 1.0 day of observed history, both fields
are `null`. Extrapolating a year from an afternoon would be a fake number.

Known bias, documented on purpose: the annual estimate extrapolates from
the season you've measured so far — June data overestimates a German
winter, December data underestimates summer. It converges as history
accumulates. (Seasonal correction is a V2 candidate.)

## 6. Payback

Only computed when `system_cost_eur > 0`:

```
recovered_eur          = lifetime.total_benefit_eur
progress_percent       = min(recovered / system_cost × 100, 100)
days_remaining         = (system_cost − recovered) / average_daily_benefit_eur
estimated_payback_date = today + days_remaining
```

- `progress_percent` is `null` when no system cost is configured.
- `estimated_payback_date` is additionally `null` while
  `average_daily_benefit_eur` is `null` (< 1 day of data).
- Already paid back → progress 100 %, date = today.
- Since `lifetime` contains measured data only, a system installed years
  before Solar Brain shows payback progress *since Solar Brain started
  measuring* — honest, if humbling. `installation_date` is returned for
  context but is **not** used to fabricate pre-measurement savings.

## 7. What V1 deliberately does NOT value

For transparency, these are not in the numbers (and why):

- **Battery arbitrage** (charging cheap, discharging at peak): needs
  battery power flow sensors and tariff windows — V2.
- **Counterfactual baselines** ("vs. a home without Solar Brain
  recommendations"): needs an attribution model; V1 measures the value of
  your *solar system*, not yet of Solar Brain's *advice*.
- **Dynamic tariffs** (Tibber/Nordpool hourly prices): single flat import
  price for now.
- **EV-specific accounting:** EV charging is part of home load economics.

## 8. API examples

`GET /api/savings/current`

```json
{
  "timestamp": "2026-06-12T10:43:00+00:00",
  "self_consumption_w": 1620.0,
  "export_w": 1640.0,
  "savings_per_hour_eur": 0.5184,
  "export_earnings_per_hour_eur": 0.1312,
  "total_benefit_per_hour_eur": 0.6496,
  "prices": {"import_eur_per_kwh": 0.32, "feed_in_eur_per_kwh": 0.08}
}
```

`GET /api/savings/summary` (abridged)

```json
{
  "today":     {"self_consumption_kwh": 6.42, "export_kwh": 4.1,
                "total_benefit_eur": 2.38, "data_coverage_hours": 11.9, "...": "..."},
  "this_week": {"total_benefit_eur": 14.77, "...": "..."},
  "this_month":{"total_benefit_eur": 27.1,  "...": "..."},
  "lifetime":  {"total_benefit_eur": 61.2,  "...": "..."},
  "average_daily_benefit_eur": 1.97,
  "estimated_annual_savings_eur": 719.05,
  "payback": {
    "system_cost_eur": 8000.0,
    "recovered_eur": 61.2,
    "progress_percent": 0.765,
    "estimated_payback_date": "2037-05-02"
  },
  "measured_since": "2026-05-12T07:01:00+00:00",
  "installation_date": "2025-04-09",
  "prices": {"import_eur_per_kwh": 0.30, "feed_in_eur_per_kwh": 0.08}
}
```

## 9. Explainability (`GET /api/savings/detail`, `/savings` page)

`GET /api/savings/detail?period=today|week|month|lifetime` returns one
period with everything needed to audit it: energy totals, the money math,
`elapsed_hours`, `coverage_percent` (= data_coverage_hours / elapsed), the
tariff used, the formulas as strings, and structured warnings:

| Code | Severity | Emitted when |
|---|---|---|
| `low_data_coverage` | warning | usable data covers < 50 % of the elapsed period (only judged after ≥ 1 h elapsed), or no telemetry exists at all |
| `default_tariff` | info | prices still equal the shipped defaults (0.30 / 0.08) — we cannot distinguish "kept default" from "really pays 0.30", hence informational |
| `no_system_cost` | info | `system_cost_eur` not configured |
| `no_payback_estimate` | info | cost configured but < 24 h of history |

The `/savings` page renders this with a period selector, the formulas
substituted with the actual numbers ("7.46 kWh × € 0.30/kWh = € 2.24"),
and the warnings as banners. Tests: `tests/test_savings_detail.py`.

## 10. Test coverage

`tests/test_savings.py` (all exact-value assertions):

1. 1 h of constant power integrates to exact kWh
2. 2 h gap credits exactly 300 s (gap rule)
3. missing values never invent energy
4. negative powers clamp to zero
5. money = energy × tariff, exactly
6. instantaneous rates incl. `null` propagation
7. payback progress/date, no-cost and already-paid-back cases
8. SQLite end-to-end: period boundaries, projections, payback
9. empty database → zeros and `null`s, never guesses

Plus `tests/test_telemetry_integration.py` step 7: both endpoints live
against a mock Home Assistant.
