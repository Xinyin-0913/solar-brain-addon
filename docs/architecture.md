# Solar Brain — Architecture

**Status:** v0.1 (post-MVP review) · **Author:** CTO review · **Date:** 2026-06-12
**Constraint that drives everything:** one solo developer, 3 months to public beta.

---

## 1. Current architecture (what exists today)

A single stateless FastAPI monolith inside a Home Assistant add-on container.

```
┌─ Home Assistant host ────────────────────────────────┐
│  ┌─ Solar Brain add-on (Docker, port 8099) ───────┐  │
│  │  FastAPI (main.py)                             │  │
│  │   ├─ GET /            HTML dashboard           │  │
│  │   ├─ GET /api/status                           │  │
│  │   ├─ GET /api/recommendation                   │  │
│  │   └─ GET /health      (Supervisor watchdog)    │  │
│  │  solar_logic.py   4 hardcoded rules            │  │
│  │  weather_client.py Open-Meteo + stub fallback  │  │
│  │  ha_client.py     optional, read-only, unused  │  │
│  │  models.py        Pydantic + config loading    │  │
│  └────────────────────────────────────────────────┘  │
│  HA Core ←(not yet actually consumed)                │
└──────────────────────────────────────────────────────┘
            │ HTTPS
            ▼
       Open-Meteo (free, keyless)
```

Honest assessment:

- **Good:** clean module boundaries already exist (logic / weather / HA / models are separate files). Config works both as add-on and standalone Docker. No state, so nothing to migrate yet.
- **Gaps:** reads zero real data from the user's home (the HA client exists but nothing calls it); no persistence; no auth on port 8099; recommendations are computed fresh on every request and forgotten.
- **Verdict:** correct skeleton for the stage we're at. Do not refactor it; extend it.

## 2. Target architecture (18–24 month view)

Principle: **local-first, cloud-optional.** The thing that runs in the home is the product. Cloud is an upsell layer, never a dependency. This matches the HA audience (privacy-sensitive, allergic to forced cloud) and keeps the solo-dev ops burden near zero until there's revenue.

```
┌─ Edge (user's home) ────────────────┐     ┌─ Cloud (later, optional) ──────┐
│  Solar Brain Agent                  │     │  Account / license service     │
│  ├─ Core engine (pure Python pkg,   │     │  AI Advisor service            │
│  │   no HA imports)                 │ ──► │   (proxy to LLM + forecast     │
│  ├─ Adapters                        │     │    models, per-site context)   │
│  │   ├─ HA adapter (entities)       │     │  Fleet dashboard (multi-site)  │
│  │   ├─ Weather adapter             │     │  Anonymized benchmark data     │
│  │   └─ Device drivers (much later) │     └────────────────────────────────┘
│  ├─ SQLite (history, decisions)     │
│  └─ FastAPI + dashboard             │
└─────────────────────────────────────┘
```

The same agent ships in three wrappers, in this order:
1. **HA add-on** (today) — distribution channel #1, zero-install for the target user.
2. **Standalone Docker container** (already works) — the "self-hosted product"; just needs docs and its own config UI polish.
3. **Cloud-managed agent** (much later) — same container, plus a license key and an outbound connection to the cloud services.

This is why the **core engine must stay a pure Python package with no HA imports**: today's `solar_logic.py` is already like this — keep it that way. Everything HA-specific stays in adapters.

## 3. What stays inside Home Assistant (forever)

- **All device I/O.** HA already has battle-tested integrations for SolarEdge, Fronius, Victron, Huawei, SMA, Growatt, etc. We consume their **entities** (sensors, numbers, selects) instead of writing inverter drivers. This is the single most important scope decision in the project: it deletes ~years of driver work.
- **Action execution.** When Solar Brain eventually acts (set battery mode, pause charging), it does so by calling HA services, so the user's existing automations, logbook, and safety nets all apply.
- **Local dashboard and notifications** (HA persistent notifications, mobile app push via HA).
- **Auth for the UI** — via HA ingress, so we never build our own login for the local product.

## 4. What moves to cloud later (and only when paid for)

| Capability | Why cloud | When |
|---|---|---|
| Accounts, license keys, billing | Can't be local by definition | First paying feature |
| AI advisor proxy | Hide our LLM API key, meter usage, swap models server-side | With Pro tier |
| Fleet view (installers, multi-home) | Cross-site by definition | B2B phase, post-PMF |
| Anonymized benchmarks ("homes like yours") | Needs aggregate data | Post-PMF |
| Remote access | Convenience upsell (HA Cloud already solves this — maybe never) | Probably never |

Rule of thumb: nothing moves to cloud because it's "more scalable." Things move to cloud only when they are impossible locally or directly monetized.

## 5. What becomes the AI service

Today's rule engine and the future AI advisor must sit behind the **same interface**:

```
Advisor.get_recommendation(context) -> Recommendation
  ├─ RuleAdvisor      (today: solar_logic.py — free tier, always works offline)
  └─ AIAdvisor        (later: LLM via cloud proxy — Pro tier)
```

- The `enable_ai` / `openrouter_api_key` options already reserve the config surface. In beta, AI calls can go **directly from the add-on to OpenRouter with the user's own key** (BYO-key) — zero cloud infrastructure for us. The cloud proxy comes later, only as the mechanism for the paid tier.
- AI scope, in order of shipping: (1) daily plain-language summary and explanation of decisions, (2) tuning of rule thresholds per home, (3) natural-language Q&A ("should I run the dishwasher now?"). **AI never directly controls hardware** — it proposes; the rule engine validates against hard safety limits; HA executes.
- The rule engine is the permanent fallback. AI down ≠ product down.

## 6. Data model from day 1

We have no DB yet (correct for MVP), but every record we start writing must already carry the fields that make SaaS and multi-site possible later. The cheap decisions now:

- **Every row has `site_id`** (constant `"default"` for now) and **UTC timestamps**.
- **Append-only snapshots**, no in-place updates — history is the future paid feature (reports, savings proof), so never throw it away.
- Storage: **SQLite in `/data`** (survives add-on restarts/updates). No Postgres until there's a cloud.

Entities (v1, keep to these six):

| Entity | Key fields | Purpose |
|---|---|---|
| `Site` | site_id, lat, lon, timezone, pv_kwp, battery_kwh | One home. Always exactly one row for now. |
| `EnergySnapshot` | site_id, ts, pv_power_w, load_power_w, battery_soc, grid_power_w | Sampled from HA entities every N minutes. |
| `WeatherSnapshot` | site_id, ts, wind_kmh, forecast_solar_kwh, source | What we believed about the weather. |
| `Recommendation` | site_id, ts, action, risk, reason, advisor ("rule"\|"ai"), inputs_json | Every recommendation ever made — the audit trail and the AI training set. |
| `ActionLog` | site_id, ts, recommendation_id, executed (bool), result | Empty until we control anything. Schema exists from day 1. |
| `EntityMapping` | site_id, role ("pv_power", "battery_soc", …), ha_entity_id | The bridge between our model and the user's HA setup. |

`Recommendation.inputs_json` (the full context the decision was made from) is the most valuable column in the product: it lets us replay decisions, debug user complaints, and later evaluate AI vs. rules.

## 7. Plugin / integration strategy

- **Phase 1 (now → beta): HA entities are the only integration surface.** A simple `EntityMapping` config ("which sensor is your PV power?") covers every inverter brand HA supports. No plugin system, no driver SDK — a config dict is the plugin system.
- **Phase 2 (post-beta): named presets.** "Victron preset", "SolarEdge preset" = pre-filled entity mappings + sensible thresholds. Still data, not code.
- **Phase 3 (only with hardware revenue in sight): driver interface.** A `Driver` ABC (`read_telemetry()`, `set_mode()`, `safe_state()`) for devices HA can't reach — primarily the **solar tracker**, which is the one piece of hardware with no good HA story and therefore our genuine hardware niche. Trackers speak Modbus/RS-485; that's a hardware-controller product decision, not an MVP one.
- Explicit non-goal: a third-party plugin marketplace. We are not a platform; we are a product. Revisit at >5k installs.

## 8. Security considerations

Current state, honestly: **port 8099 is open on the LAN with no auth.** Acceptable for a read-only MVP on a trusted network; not acceptable once we store history or trigger actions.

Priorities, in order:

1. **HA ingress (next sprint).** Serve the UI through HA's authenticated ingress; stop exposing 8099 by default (keep it as an opt-out for the standalone Docker use case). This buys real auth for ~a day of work.
2. **Secrets hygiene.** Tokens already use `password` schema in `config.yaml` (masked in UI). Never log tokens or API keys; never include them in `inputs_json`; never send HA tokens or entity names that reveal identity to the LLM.
3. **AI data boundary.** Document exactly what leaves the house when `enable_ai` is on (numeric telemetry + location-rounded weather, nothing else). Opt-in, off by default. This is a selling point to this audience, not just compliance.
4. **Action safety (before any control ships).** Hard-coded safety envelope in the rule engine (e.g., never discharge battery below floor, always allow safe-mode), every action written to `ActionLog` first, dry-run mode default-on for the first release, and a physical-world rule: **the add-on must never be the only thing capable of putting hardware in a safe state.**
5. **Supply chain basics.** Pinned dependencies (done), add-on built locally by Supervisor (done), signed releases when we publish the repo.
6. **Later (cloud phase):** per-site API keys, TLS everywhere, EU data residency decision before the first European paying customer (this is a GDPR product the moment cloud accounts exist).

## 9. Decisions log

| # | Decision | Why |
|---|---|---|
| 1 | Local-first, cloud-optional | Audience fit, zero ops cost, privacy as a feature |
| 2 | Consume HA entities, never write inverter drivers | Deletes the largest possible scope |
| 3 | Core engine = pure Python pkg behind `Advisor` interface | Enables AI swap and standalone product for free |
| 4 | SQLite, append-only, `site_id` + UTC on every row from day 1 | Cheapest possible future-proofing |
| 5 | BYO OpenRouter key in beta, cloud proxy only with paid tier | Zero infra until revenue |
| 6 | Tracker control is the hardware niche; everything else via HA | Only build hardware where HA has no answer |
