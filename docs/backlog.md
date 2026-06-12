# Solar Brain — Prioritized Backlog

Prioritization lens: **does this get us to 50 real beta users who believe the product saves them money?** Everything is scored against that, not against architectural beauty.

Effort: **S** ≤ 1 day · **M** 2–4 days · **L** ~1 week+ (solo-dev days, including testing and docs).

---

## Must Have (weeks 1–4 — without these there is no product)

| # | Item | Effort | Why it's a must |
|---|---|---|---|
| M1 | Entity mapping config (`pv_power`, `load_power`, `battery_soc`, `grid_power` → HA entity IDs) | M | The bridge to real data; everything below depends on it |
| M2 | Poll mapped HA entities every 5 min via existing `ha_client.py` | S | The product currently reads nothing from the home |
| M3 | Recommendations use real telemetry (battery SOC, PV vs. load) | M | "Demo" → "product" |
| M4 | HA ingress (auth'd dashboard in HA sidebar; stop default-exposing :8099) | S | Closes the no-auth hole and improves UX in one move |
| M5 | SQLite persistence in `/data`: snapshots + every recommendation (`site_id` + UTC from day 1) | M | History is the future savings report and the audit trail |
| M6 | Dashboard "today" view: PV vs. load chart + recent recommendations | M | Users need to *see* it working to trust it |
| M7 | HA persistent/mobile notification on recommendation *change* | S | The advisor must reach users where they live |
| M8 | Expose `sensor.solar_brain_recommendation` (+ risk) back to HA | S | Lets power users automate on top of us — cheap, huge goodwill |
| M9 | Publish GitHub add-on repo; install = paste URL; README with screenshots | M | Distribution. A product nobody can install doesn't exist |
| M10 | Error visibility: last errors on dashboard, graceful handling of missing entities / HA restarts | M | Tester #1's broken setup is the real test suite |
| M11 | Recruit and onboard 5–10 real testers | M | A deliverable, not marketing fluff — gates everything in weeks 5+ |

## Should Have (weeks 5–12 — beta differentiators)

| # | Item | Effort | Why |
|---|---|---|---|
| S1 | `Advisor` interface; rule engine refactored behind it | S | One contained refactor that makes AI pluggable |
| S2 | AI daily summary via user's own OpenRouter key (opt-in, numbers-only data boundary, documented) | L | The differentiator vs. EMHASS/Predbat; zero infra via BYO-key |
| S3 | Savings estimator (history × configurable electricity price) + weekly report | L | The future paywall's justification — must exist before any pricing talk |
| S4 | Configurable rule thresholds + battery-aware rules ("battery full + sun → run heavy loads") | M | First thing real users will ask to tune |
| S5 | Whitelisted actions as HA service calls: dry-run default, per-action opt-in, `ActionLog` | L | First step from advisor to controller, on training wheels |
| S6 | Storm safe-mode: trigger a user-chosen HA script + push alert (free forever) | M | Highest-value action, clearest story, ethically must stay free |
| S7 | First-run onboarding flow (guided entity mapping, sanity checks) | M | Beta users churn in the first 10 minutes or never |
| S8 | Opt-in anonymous telemetry (installs, feature usage, error counts only) | M | Post-beta decisions need data; opt-in preserves trust |
| S9 | Feedback affordance: "was this recommendation useful? 👍/👎" stored with the recommendation | S | Cheapest possible PMF signal, and future AI eval data |
| S10 | Standalone-Docker docs polish (the self-hosted, non-HA story) | S | Already works; just make it official |

## Nice To Have (only if beta feedback demands them)

| # | Item | Effort | Trigger to build |
|---|---|---|---|
| N1 | Per-brand presets (Victron/SolarEdge/Fronius entity mappings + thresholds) | M | ≥3 testers with the same brand struggle with mapping |
| N2 | Electricity price API integration (dynamic tariffs: Tibber/Nordpool/awattar) | M | Testers on dynamic tariffs ask — likely, in EU |
| N3 | Natural-language Q&A ("should I run the dryer now?") | M | AI summary (S2) lands well |
| N4 | Energy-flow visualization (animated PV→battery→home diagram) | M | Pure delight; after function is proven |
| N5 | i18n (DE first — Germany is the PV market) | M | Non-English feedback shows up |
| N6 | Longer-horizon planning (tomorrow's plan from 48 h forecast) | L | Daily summary proves valuable first |
| N7 | Backup/restore of settings + history | S | First "I reinstalled and lost everything" report |
| N8 | MQTT publishing (alternative to REST sensors) | S | Multiple users ask; not before |

## Do Not Build Yet (parking lot — revisit only at the stated trigger)

| Item | Trigger to revisit |
|---|---|
| Cloud SaaS: accounts, managed AI proxy, billing | Beta users explicitly ask to pay (target: month 5–6) |
| Payment/licensing integration (Lemon Squeezy/Paddle) | Same as above — sell only what beta validated |
| Direct hardware control (Modbus/RS-485, battery/inverter writes) | Software revenue exists; liability understood |
| Solar tracker controller (hardware product) | Post-PMF, funded, fractional support help hired |
| Installer/fleet multi-site dashboard | An actual installer asks, twice |
| ML forecasting (custom models) | Telemetry from hundreds of homes exists |
| Mobile app | Probably never — HA companion app covers it |
| Custom frontend framework (React/Vue) | Vanilla HTML demonstrably blocks a needed feature |
| Postgres / Kubernetes / microservices | Something visibly breaks at current scale (it won't) |
| Plugin SDK / marketplace | >5k installs and concrete third-party demand |
| EV-charger smart charging | Big and real — but evcc owns it; needs a differentiated angle first |

---

## Sequencing notes (solo-dev reality)

- Capacity ≈ 4 focused days/week after support, docs, and community time — the Must list above is ~4 weeks at that pace, with zero slack. If something slips, cut **M6 chart polish** and **M8**, never M9–M11 (distribution and testers).
- Every week from week 4 onward reserves ~20% for tester support. Unbudgeted support is how solo projects die.
- Re-rank Should/Nice every 2 weeks against actual tester feedback. The backlog is a hypothesis; the testers are the data.
