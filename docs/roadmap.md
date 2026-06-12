# Solar Brain — Roadmap

**Constraint:** one solo developer, ~3 months (12 weeks) to public beta.
**Strategy:** ship to real Home Assistant users as early as week 4. Everything after that is shaped by their feedback, not this document.

The single biggest gap in the current MVP: **it doesn't read any real data from the user's home.** Until it does, it's a demo, not a product. Weeks 1–4 fix exactly that.

---

## Phase 1 — MVP that earns the name (Weeks 1–4)

Goal: a stranger can install it from a GitHub URL, connect their real PV system in under 10 minutes, and see recommendations based on **their** data.

### Week 1 — Real data in
- Entity mapping config: user picks which HA entities are `pv_power`, `load_power`, `battery_soc`, `grid_power` (add-on options first; UI picker later).
- Actually use `ha_client.py`: poll mapped entities every 5 minutes.
- Recommendations now use real PV/battery/load values, not just time-of-day and weather.
- HA ingress so the dashboard is reachable (authenticated) from the HA sidebar.

### Week 2 — Memory
- SQLite in `/data` with the six v1 tables (see architecture.md §6).
- Persist energy snapshots, weather snapshots, and every recommendation.
- Dashboard: "today" view — simple line chart (PV vs. load), last 10 recommendations. No charting library rabbit holes; one canvas chart or a static SVG is fine.

### Week 3 — Be heard
- Push recommendations as HA persistent notifications (and therefore HA mobile push) when the recommendation *changes* — not on a timer. Nobody wants "use solar energy" every 5 minutes.
- Expose Solar Brain's state back to HA as sensors via the REST API (e.g., `sensor.solar_brain_recommendation`) so users can build their own automations on top of it. This is huge for the HA audience and costs little.
- Rule engine v2: thresholds configurable, rules use real battery SOC ("battery full + sun → run heavy loads now").

### Week 4 — Shippable
- Publish the add-on repository on GitHub (the `repository.yaml` is ready); install = paste one URL.
- README with screenshots, honest limitations list.
- Error visibility: last errors shown on the dashboard, clean logs.
- Recruit 5–10 testers (HA community forum thread, r/homeassistant). **This is a deliverable, not an afterthought.**

**Week 4 exit criteria:** ≥5 strangers running it on real systems, and we can see (from their feedback, not telemetry) whether recommendations are ever useful.

---

## Phase 2 — Beta (Weeks 5–12)

Ordered by value-of-learning, not engineering elegance. Re-plan every 2 weeks against tester feedback — expect to delete some of this.

### Weeks 5–6 — AI advisor v1 (the differentiator)
- `Advisor` interface; rule advisor refactored behind it (small, contained refactor).
- AI advisor with **user's own OpenRouter key** (BYO-key, zero infra): daily morning summary in plain language — "Cloudy until noon, battery at 40%, delay the washing machine until 13:00."
- Strict data boundary (numbers only, documented), opt-in, rule engine always the fallback.

### Weeks 7–8 — Prove the money
- Savings estimator: using stored history + a configurable electricity price, show "Solar Brain recommendations were worth ~€X this week" (estimate, clearly labeled). This is the future paywall justification, so it must exist *before* the paywall.
- Weekly report on dashboard + as notification.

### Weeks 9–10 — First actions (carefully)
- Execute a *small whitelist* of recommendations as HA service calls — user-approved per action type, dry-run mode default-on, everything logged to `ActionLog`.
- Start with the safest, highest-value one: storm safe-mode trigger (e.g., notify + optionally run a user-chosen HA script). Avoid direct battery/inverter writes in beta.

### Weeks 11–12 — Beta launch
- Onboarding polish: first-run flow that holds the user's hand through entity mapping.
- Opt-in anonymous telemetry (install count, feature usage, error counts — nothing else) so post-beta decisions use data.
- Hardening: graceful handling of HA restarts, missing entities, corrupt DB.
- Launch: HA forum, r/homeassistant, a short demo video. Set up a feedback channel (GitHub issues + one Discord/forum thread).

**Week 12 exit criteria:** ≥50 active installs, ≥10 users who say the savings report is roughly believable, a ranked list of what they'd pay for.

---

## What NOT to build yet (and when to reconsider)

| Not building | Why not | Reconsider when |
|---|---|---|
| Cloud SaaS, accounts, billing infra | Zero users, zero revenue, massive ops cost for one person | A paid tier is validated (post-beta) |
| Mobile app | HA companion app already delivers push and dashboards | Never, probably |
| Direct inverter/battery drivers (Modbus etc.) | HA integrations already do it better | A hardware product is funded |
| Solar tracker control | Real niche, but hardware + safety scope is a company, not a sprint | Post-PMF, with revenue |
| Custom frontend framework (React etc.) | Vanilla HTML is shipping fine; rewrite costs weeks, earns nothing | UI complexity genuinely hurts (not before) |
| ML forecasting models | Open-Meteo + rules + LLM summaries are enough to learn from | Data from hundreds of homes exists |
| Multi-site / multi-tenant | One home per install is the entire current market | B2B installer interest is real |
| Plugin SDK / marketplace | We're a product, not a platform | >5k installs |
| Postgres, Kubernetes, microservices | SQLite + one container fits this product for years | It visibly breaks |

The pattern: nothing gets built because the *architecture* wants it. Things get built because *users at the current stage* need them.
