# Solar Brain — Product Mockups

Five screens in modern Home Assistant style (dark theme, HA sidebar/chrome,
HA energy colors). Each `.png` was rendered from the matching `.html` —
edit the HTML and re-screenshot to iterate.

| File | What it shows | Status |
|---|---|---|
| `dashboard_v1.png` | The add-on as implemented today (v0.2): live telemetry, rule-based recommendation, status | **Matches current build** |
| `dashboard_v2.png` | Target V1 dashboard: live energy flow, today's stats incl. € saved, production-vs-load chart, advisor timeline | Target (weeks 2–8) |
| `settings_entities.png` | Entity mapping with auto-detected suggestions and manual override | Matches current build (visual polish target) |
| `savings_page.png` | Weekly savings report — the Pro tier's reason to exist | Target (weeks 7–8) |
| `mobile_view.png` | The same product on a phone via the HA companion app | Target |

## User journey

1. **Install** the add-on from the GitHub repo URL, start it, click "Solar
   Brain" in the HA sidebar.
2. **Connect** (`settings_entities.png`): Solar Brain has already scanned HA
   and pre-selected the user's PV, battery, grid and EV sensors — review,
   fix one dropdown at most, Save. Under 2 minutes.
3. **See it live** (`dashboard_v1.png` → `dashboard_v2.png`): telemetry
   appears within a minute; over days the dashboard fills with the energy
   flow, charts, and an advisor that says *what to do right now* and what
   it's worth in euros.
4. **Get reached, not checked**: recommendations arrive as HA notifications
   on the phone (`mobile_view.png`) — the dashboard is for browsing, the
   push is the product.
5. **Believe the value** (`savings_page.png`): the weekly savings report
   ("€ 17.20 this week, € 270/year pace") is what converts a curious
   tinkerer into a Pro subscriber.
