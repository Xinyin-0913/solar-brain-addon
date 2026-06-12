# Solar Brain — Monetization

**Hard truth first:** the initial market (Home Assistant power users) is the most monetization-hostile audience on the internet — they self-host specifically to avoid subscriptions, and strong free alternatives exist (EMHASS, Predbat, evcc are free and open source). That is *fine*: they are the distribution channel and the credibility engine, not the revenue base. Revenue comes from the layer above the free core, and later from people who want the outcome without the tinkering.

**Pricing anchor:** a typical residential PV+battery home can plausibly gain €50–€300/year from smarter energy timing. Any price must stay clearly below the believable savings we *show* the user (this is why the savings report ships in beta, before any paywall).

---

## 1. Business models considered

| Model | Verdict | Notes |
|---|---|---|
| Freemium add-on + Pro subscription | ✅ **Primary** | Free local core, paid AI/reports layer |
| One-time Pro license | ✅ Offer alongside | This audience strongly prefers it; price it like ~2 years of subscription |
| BYO-key (user pays OpenRouter directly) | ✅ Forever-free path | Keeps trust, costs us nothing, caps what free riders cost |
| Hardware controller (tracker/relay box) | 🟡 Later | Real margin, real moat — and real liability + support burden. Post-PMF only |
| B2B: installer fleet dashboard | 🟡 Later | Best long-term revenue per customer; needs cloud + ~1 year of credibility |
| Donations / sponsorware | ❌ Not a business | Accept them, don't plan on them |
| Ads / selling data | ❌ Never | Would kill the product in this community overnight |

## 2. Free version (forever free, local, open core)

Everything needed to be genuinely useful — crippleware would be sniffed out and forked:

- Rule-based recommendations with real HA data
- Dashboard, history (e.g., 90 days local retention), HA sensors + notifications
- Storm safe-mode alerts
- AI summaries **with your own OpenRouter key** (BYO-key)

The free tier's job: 10k installs, community trust, the funnel.

## 3. Paid version — "Solar Brain Pro"

Target: **€4–6/month or €49/year**, or one-time license ~€99. Sold via Lemon Squeezy or Paddle (merchant of record handles VAT — non-negotiable for a solo EU-facing dev). License key pasted into add-on options; no account system in v1 of payments.

What's behind the paywall (convenience and intelligence, never safety):

- **Managed AI advisor** — no API key hassle, our cloud proxy, better/tuned models, daily plan, natural-language Q&A
- **Savings & performance reports** — weekly/monthly PDF-quality reports, year-over-year, export
- **Adaptive thresholds** — rules that tune themselves to the home from its history
- Longer history retention + cloud backup of settings
- Priority support

Explicit principle: **safety features are never paid.** Storm protection stays free forever — charging for "your tracker survives the storm" is both ethically wrong and a PR disaster waiting to happen.

## 4. Subscription model mechanics

- Subscription exists because of genuinely recurring costs: LLM inference, weather/forecast API tiers, support. Communicate exactly that — this audience respects honest cost-based pricing.
- One-time license covers the same features with BYO-key economics where possible; managed-AI quota for one-time buyers is the only soft limit.
- Grace degradation: if a subscription lapses, the product falls back to the free tier — never bricks, never deletes local data. (Again: trust is the moat.)
- Milestone to launch payments: **only after the beta proves people ask for the Pro features.** Target: first paying customer ~month 5–6, 100 paying ≈ €500 MRR by month 9–12. Modest — this funds the next phase, it is not yet a salary.

## 5. Hardware controller model (the long game)

The genuine niche: **solar trackers** (and dumb-relay setups) have no good Home Assistant story. Options, in order of increasing commitment:

1. **Certified-hardware preset** (cheap to try): sell a "Solar Brain Ready" guide + preset for an off-the-shelf ESP32/relay or Shelly-based setup the user buys themselves. Software margin, no inventory.
2. **Solar Brain Controller** — a small box (ESPHome-based, Modbus/RS-485) flashed and sold by us, ~€99–199, that brings tracker/legacy inverter control into HA. Hardware margin ~30–40%, plus it pulls Pro subscriptions.
3. **Partnerships** — license the brain to tracker/inverter manufacturers as their "smart mode." Highest leverage, only reachable with install-base proof.

Honest warning for a solo dev: hardware = inventory, certification (CE), returns, and "it doesn't work with my 2009 inverter" support. Do not start before software revenue funds at least fractional help.

## 6. Why users would pay (in their words)

1. *"It pays for itself."* The weekly report says it saved €4.10 this week; Pro costs €1.15/week. Decision made. — the savings report is the sales team.
2. *"I don't want to manage an API key and prompts."* Managed AI is pure convenience upsell, the classic open-core move.
3. *"I want the plan, not the data."* "Run the dishwasher at 13:00" beats reading Grafana — increasingly true as we reach beyond tinkerers to normal PV owners (the actual residential market, ~10–100× larger).
4. *"My hardware is finally supported."* Tracker/legacy owners have no alternative; the controller is the only product in the lineup with no free substitute.
5. *"I trust it."* Local-first, safety-is-free, lapse-doesn't-brick. Trust converts this audience; lock-in repels it.

## 7. What we will not do

- No ads, no data selling, no forced cloud, no feature ransom of previously free features (the community never forgets).
- No "contact sales" enterprise theater before there's an actual installer asking for it.
- No price below €3/month — too small to matter, still 100% of the support load.
