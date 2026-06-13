"""Inline HTML pages (no frontend framework by design).

All links and fetch() calls use relative URLs so the pages work both on
direct port access and behind Home Assistant ingress.
"""

_BASE_CSS = """
  :root {
    --bg: #0e1116;
    --card: #181d26;
    --border: #2a3140;
    --text: #e8ebf0;
    --muted: #8a93a5;
    --accent: #f2b22d;
    --low: #3ecf8e;
    --medium: #f2b22d;
    --high: #f25c5c;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: "Segoe UI", system-ui, sans-serif;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    padding: 48px 20px;
  }
  .container { width: 100%; max-width: 720px; }
  header { display: flex; align-items: center; gap: 14px; margin-bottom: 32px; }
  .logo {
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, var(--accent), #f28a2d);
    display: flex; align-items: center; justify-content: center;
    font-size: 22px;
  }
  h1 { font-size: 22px; font-weight: 600; letter-spacing: 0.3px; }
  header small { color: var(--muted); display: block; font-size: 12px; }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 18px;
  }
  .card h2 {
    font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px;
    color: var(--muted); margin-bottom: 16px; font-weight: 600;
  }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
  .label { color: var(--muted); font-size: 12px; margin-bottom: 4px; }
  .value { font-size: 15px; font-weight: 500; }
  .muted { color: var(--muted); }
  a { color: var(--accent); text-decoration: none; }
  footer { text-align: center; color: var(--muted); font-size: 12px; margin-top: 24px; }
  .btn {
    background: var(--accent); color: #14171c; border: none; cursor: pointer;
    padding: 10px 22px; border-radius: 10px; font-size: 14px; font-weight: 600;
  }
  .btn.secondary { background: transparent; color: var(--accent); border: 1px solid var(--border); }
  .btn:disabled { opacity: .5; cursor: default; }
"""

DASHBOARD_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar Brain</title>
<style>
{_BASE_CSS}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
  .recommendation {{ font-size: 18px; font-weight: 600; margin-bottom: 10px; }}
  .reason {{ color: var(--muted); font-size: 14px; line-height: 1.5; }}
  .badge {{
    display: inline-block; padding: 4px 12px; border-radius: 999px;
    font-size: 12px; font-weight: 600; margin-top: 14px;
  }}
  .badge.low {{ background: rgba(62,207,142,.12); color: var(--low); }}
  .badge.medium {{ background: rgba(242,178,45,.12); color: var(--medium); }}
  .badge.high {{ background: rgba(242,92,92,.12); color: var(--high); }}
  .tag {{ font-size: 10px; color: var(--muted); }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">&#9728;</div>
    <div>
      <h1>Solar Brain</h1>
      <small>Smart solar energy advisor</small>
    </div>
  </header>

  <div class="card">
    <h2>Live telemetry</h2>
    <div class="grid" id="telemetry-grid">
      <div><div class="label">Solar</div><div class="value" id="tel-solar">&hellip;</div></div>
      <div><div class="label">Battery</div><div class="value" id="tel-batt">&hellip;</div></div>
      <div><div class="label">Home load</div><div class="value" id="tel-load">&hellip;</div></div>
      <div><div class="label">Grid import</div><div class="value" id="tel-import">&hellip;</div></div>
      <div><div class="label">Grid export</div><div class="value" id="tel-export">&hellip;</div></div>
      <div><div class="label">EV charging</div><div class="value" id="tel-ev">&hellip;</div></div>
    </div>
    <div class="muted" id="telemetry-note" style="margin-top:14px;font-size:12px;"></div>
  </div>

  <div class="card">
    <h2>Savings</h2>
    <div class="grid">
      <div><div class="label">Today</div><div class="value" id="sv-today">&hellip;</div></div>
      <div><div class="label">This week</div><div class="value" id="sv-week">&hellip;</div></div>
      <div><div class="label">This month</div><div class="value" id="sv-month">&hellip;</div></div>
      <div><div class="label">Lifetime</div><div class="value" id="sv-life">&hellip;</div></div>
      <div><div class="label">Est. annual</div><div class="value" id="sv-annual">&hellip;</div></div>
      <div><div class="label">Payback</div><div class="value" id="sv-payback">&hellip;</div></div>
      <div><div class="label">Payback date</div><div class="value" id="sv-paydate">&hellip;</div></div>
    </div>
    <div class="muted" id="savings-note" style="margin-top:14px;font-size:12px;"></div>
    <div style="margin-top:10px;font-size:12px;"><a href="savings">How are these numbers calculated? &rarr;</a></div>
  </div>

  <div class="card">
    <h2>Recommendation</h2>
    <div class="recommendation" id="rec-text">&hellip;</div>
    <div class="reason" id="rec-reason"></div>
    <span class="badge low" id="rec-risk">&hellip;</span>
  </div>

  <div class="card">
    <h2>Status</h2>
    <div class="grid2">
      <div><div class="label">Add-on</div><div class="value" id="addon-status">&hellip;</div></div>
      <div><div class="label">Time</div><div class="value" id="current-time">&hellip;</div></div>
      <div><div class="label">Location</div><div class="value" id="location">&hellip;</div></div>
      <div><div class="label">Home Assistant</div><div class="value" id="ha-mode">&hellip;</div></div>
    </div>
    <div class="muted" id="ha-connection" style="margin-top:14px;font-size:12px;"></div>
  </div>

  <footer>
    <a href="devices">Smart home energy</a> &middot;
    <a href="savings">Savings details</a> &middot;
    <a href="settings/entities">Entity mapping</a> &middot;
    <a href="api/status">/api/status</a> &middot;
    <a href="api/telemetry/current">/api/telemetry/current</a>
  </footer>
</div>

<script>
function fmtW(v) {{
  if (v === null || v === undefined) return '\\u2014';
  return Math.abs(v) >= 1000 ? (v / 1000).toFixed(2) + ' kW' : Math.round(v) + ' W';
}}

async function refreshTelemetry() {{
  const note = document.getElementById('telemetry-note');
  try {{
    const res = await fetch('api/telemetry/current');
    if (!res.ok) {{
      const body = await res.json().catch(() => ({{}}));
      note.innerHTML = (body.detail || 'Telemetry unavailable.') +
        ' <a href="settings/entities">Open entity mapping &rarr;</a>';
      return;
    }}
    const t = await res.json();
    document.getElementById('tel-solar').textContent = fmtW(t.solar_power_w);
    document.getElementById('tel-batt').textContent =
      t.battery_soc === null ? '\\u2014' : t.battery_soc.toFixed(0) + ' %';
    document.getElementById('tel-load').textContent = fmtW(t.home_load_w) +
      (t.estimated_fields.includes('home_load_w') ? ' (est.)' : '');
    document.getElementById('tel-import').textContent = fmtW(t.grid_import_w);
    document.getElementById('tel-export').textContent = fmtW(t.grid_export_w);
    document.getElementById('tel-ev').textContent = fmtW(t.ev_power_w);
    if (t.missing_roles.length === 6) {{
      note.innerHTML = 'No entities mapped yet. ' +
        '<a href="settings/entities">Map your sensors &rarr;</a>';
    }} else if (t.missing_roles.length > 0) {{
      note.textContent = 'No data for: ' + t.missing_roles.join(', ');
    }} else {{
      note.textContent = '';
    }}
  }} catch (err) {{
    note.textContent = 'Failed to load telemetry: ' + err;
  }}
}}

async function refresh() {{
  try {{
    const [status, rec] = await Promise.all([
      fetch('api/status').then(r => r.json()),
      fetch('api/recommendation').then(r => r.json()),
    ]);
    document.getElementById('addon-status').textContent = status.addon_status;
    document.getElementById('current-time').textContent =
      new Date(status.current_time).toLocaleString();
    document.getElementById('location').textContent = status.location;
    document.getElementById('ha-mode').textContent =
      status.ha_mode + ' \\u00b7 ' + status.ha_auth.replace(/_/g, ' ') +
      (status.ha_reachable ? '' : ' \\u00b7 offline');
    document.getElementById('ha-connection').textContent = status.ha_connection;
    document.getElementById('rec-text').textContent = rec.recommendation_text;
    document.getElementById('rec-reason').textContent = rec.reason;
    const badge = document.getElementById('rec-risk');
    badge.textContent = 'risk: ' + rec.risk_level;
    badge.className = 'badge ' + rec.risk_level;
  }} catch (err) {{
    document.getElementById('rec-text').textContent = 'Failed to load data';
    document.getElementById('rec-reason').textContent = String(err);
  }}
}}

function fmtEur(v) {{
  return (v === null || v === undefined) ? '\\u2014' : '\\u20ac ' + v.toFixed(2);
}}

async function refreshSavings() {{
  const note = document.getElementById('savings-note');
  try {{
    const res = await fetch('api/savings/summary');
    if (!res.ok) {{ note.textContent = 'Savings unavailable.'; return; }}
    const s = await res.json();
    document.getElementById('sv-today').textContent = fmtEur(s.today.total_benefit_eur);
    document.getElementById('sv-week').textContent = fmtEur(s.this_week.total_benefit_eur);
    document.getElementById('sv-month').textContent = fmtEur(s.this_month.total_benefit_eur);
    document.getElementById('sv-life').textContent = fmtEur(s.lifetime.total_benefit_eur);
    document.getElementById('sv-annual').textContent =
      s.estimated_annual_savings_eur === null
        ? '\\u2014 (needs 24 h of data)' : fmtEur(s.estimated_annual_savings_eur);
    document.getElementById('sv-payback').textContent =
      s.payback.progress_percent === null
        ? '\\u2014 (set system_cost_eur)' : s.payback.progress_percent.toFixed(1) + ' %';
    document.getElementById('sv-paydate').textContent =
      s.payback.estimated_payback_date || '\\u2014';
    let info = 'tariff \\u20ac ' + s.prices.import_eur_per_kwh.toFixed(2) +
      '/kWh \\u00b7 feed-in \\u20ac ' + s.prices.feed_in_eur_per_kwh.toFixed(2) + '/kWh';
    if (s.measured_since) {{
      info += ' \\u00b7 measured since ' + new Date(s.measured_since).toLocaleDateString();
    }} else {{
      info += ' \\u00b7 no telemetry history yet \\u2014 map your entities first';
    }}
    note.textContent = info;
  }} catch (err) {{
    note.textContent = 'Failed to load savings: ' + err;
  }}
}}

refresh();
refreshTelemetry();
refreshSavings();
setInterval(refresh, 60000);
setInterval(refreshTelemetry, 30000);
setInterval(refreshSavings, 60000);
</script>
</body>
</html>
"""

SAVINGS_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar Brain &middot; Savings</title>
<style>
{_BASE_CSS}
  .seg {{ display: flex; gap: 6px; background: #11151c; border: 1px solid var(--border);
         border-radius: 12px; padding: 5px; margin-bottom: 18px; }}
  .seg button {{ flex: 1; background: transparent; border: none; color: var(--muted);
                 padding: 9px 0; border-radius: 9px; font-size: 13.5px; cursor: pointer;
                 font-family: inherit; }}
  .seg button.on {{ background: rgba(242,178,45,.15); color: var(--accent); font-weight: 600; }}
  .banner {{ display: flex; gap: 10px; border-radius: 12px; padding: 12px 15px;
             font-size: 13px; line-height: 1.5; margin-bottom: 10px; }}
  .banner.warning {{ background: rgba(242,178,45,.09); border: 1px solid rgba(242,178,45,.4);
                     color: #f4cf7e; }}
  .banner.info {{ background: rgba(24,188,242,.07); border: 1px solid rgba(24,188,242,.3);
                  color: #9bd8ef; }}
  .total {{ font-size: 38px; font-weight: 800; color: var(--low); }}
  .total-sub {{ color: var(--muted); font-size: 13px; margin: 4px 0 18px; }}
  .rows {{ border-top: 1px solid var(--border); }}
  .row {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px;
          padding: 12px 2px; border-bottom: 1px solid #232a35; font-size: 14px; }}
  .row .k {{ color: var(--muted); }}
  .row .math {{ color: #5f6877; font-size: 12px; text-align: right; display: block; }}
  .row .v {{ font-weight: 600; text-align: right; }}
  .row.total-row .v {{ color: var(--low); font-size: 16px; }}
  .formula {{ font-size: 13px; line-height: 1.8; color: var(--muted); }}
  .formula code {{ color: var(--text); background: #11151c; padding: 2px 8px;
                   border-radius: 6px; font-size: 12.5px; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">&euro;</div>
    <div>
      <h1>Savings &mdash; explained</h1>
      <small>Every number, with the math next to it</small>
    </div>
  </header>

  <div class="seg" id="seg">
    <button data-p="today" class="on">Today</button>
    <button data-p="week">This week</button>
    <button data-p="month">This month</button>
    <button data-p="lifetime">Lifetime</button>
  </div>

  <div id="banners"></div>

  <div class="card">
    <h2 id="period-title">Today</h2>
    <div class="total" id="d-total">&hellip;</div>
    <div class="total-sub" id="d-range"></div>
    <div class="rows">
      <div class="row"><span class="k">Self-consumed solar</span><span class="v" id="d-sc-kwh">&hellip;</span></div>
      <div class="row"><span class="k">Exported to grid</span><span class="v" id="d-ex-kwh">&hellip;</span></div>
      <div class="row">
        <span class="k">Import-price savings<span class="math" id="m-sc"></span></span>
        <span class="v" id="d-sc-eur">&hellip;</span>
      </div>
      <div class="row">
        <span class="k">Feed-in earnings<span class="math" id="m-ex"></span></span>
        <span class="v" id="d-ex-eur">&hellip;</span>
      </div>
      <div class="row total-row"><span class="k">Total value</span><span class="v" id="d-total2">&hellip;</span></div>
      <div class="row"><span class="k">Data coverage</span><span class="v" id="d-cov">&hellip;</span></div>
      <div class="row"><span class="k">Tariff used</span><span class="v" id="d-tariff">&hellip;</span></div>
    </div>
  </div>

  <div class="card">
    <h2>How these numbers are made</h2>
    <div class="formula">
      <div><code>self-consumption savings = self-consumed kWh &times; import price</code></div>
      <div><code>export earnings = exported kWh &times; feed-in tariff</code></div>
      <div><code>total value = self-consumption savings + export earnings</code></div>
      <div style="margin-top:8px;">Energy comes from telemetry sampled every 60&nbsp;s:
        <code>energy = &Sigma; power(t&#7522;) &times; min(t&#7522;&#8330;&#8321; &minus; t&#7522;, 300&nbsp;s)</code></div>
      <div style="margin-top:8px;">Gaps longer than 5 minutes are <b>not</b> credited &mdash; missing
        data always lowers the result, never raises it. No projections are shown
        with less than 24&nbsp;h of history.</div>
    </div>
  </div>

  <footer><a href="./">&larr; Back to dashboard</a></footer>
</div>

<script>
const TITLES = {{today: 'Today', week: 'This week', month: 'This month', lifetime: 'Lifetime'}};
const eur = v => '\\u20ac ' + v.toFixed(2);

async function load(period) {{
  document.querySelectorAll('#seg button').forEach(b =>
    b.className = b.dataset.p === period ? 'on' : '');
  try {{
    const res = await fetch('api/savings/detail?period=' + period);
    if (!res.ok) return;
    const d = await res.json();
    const s = d.savings, p = d.prices;
    document.getElementById('period-title').textContent = TITLES[period];
    document.getElementById('d-total').textContent = eur(s.total_benefit_eur);
    document.getElementById('d-range').textContent = d.period_start
      ? 'from ' + new Date(d.period_start).toLocaleString() + ' to now'
      : 'no data recorded yet';
    document.getElementById('d-sc-kwh').textContent = s.self_consumption_kwh.toFixed(2) + ' kWh';
    document.getElementById('d-ex-kwh').textContent = s.export_kwh.toFixed(2) + ' kWh';
    document.getElementById('d-sc-eur').textContent = eur(s.self_consumption_savings_eur);
    document.getElementById('m-sc').textContent =
      s.self_consumption_kwh.toFixed(2) + ' kWh \\u00d7 \\u20ac ' +
      p.import_eur_per_kwh.toFixed(2) + '/kWh';
    document.getElementById('d-ex-eur').textContent = eur(s.export_earnings_eur);
    document.getElementById('m-ex').textContent =
      s.export_kwh.toFixed(2) + ' kWh \\u00d7 \\u20ac ' +
      p.feed_in_eur_per_kwh.toFixed(2) + '/kWh';
    document.getElementById('d-total2').textContent = eur(s.total_benefit_eur);
    document.getElementById('d-cov').textContent =
      s.data_coverage_hours.toFixed(1) + ' h' +
      (d.coverage_percent !== null ? ' (' + d.coverage_percent.toFixed(0) + ' %)' : '');
    document.getElementById('d-tariff').textContent =
      '\\u20ac ' + p.import_eur_per_kwh.toFixed(2) + '/kWh \\u00b7 feed-in \\u20ac ' +
      p.feed_in_eur_per_kwh.toFixed(2) + '/kWh' + (d.tariff_is_default ? ' (default)' : '');

    const banners = document.getElementById('banners');
    banners.innerHTML = '';
    d.warnings.forEach(w => {{
      const div = document.createElement('div');
      div.className = 'banner ' + w.severity;
      div.textContent = (w.severity === 'warning' ? '\\u26a0 ' : '\\u2139 ') + w.message;
      banners.appendChild(div);
    }});
  }} catch (err) {{
    document.getElementById('d-total').textContent = 'Failed: ' + err;
  }}
}}

document.querySelectorAll('#seg button').forEach(b =>
  b.addEventListener('click', () => load(b.dataset.p)));
load('today');
setInterval(() => {{
  const on = document.querySelector('#seg button.on');
  load(on ? on.dataset.p : 'today');
}}, 60000);
</script>
</body>
</html>
"""

DEVICES_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar Brain &middot; Smart home energy</title>
<style>
{_BASE_CSS}
  .summary {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; }}
  .summary .v {{ font-size: 20px; font-weight: 700; }}
  .v.eur {{ color: var(--low); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: right; padding: 9px 10px; border-bottom: 1px solid #232a35; }}
  th {{ color: var(--muted); font-size: 11px; text-transform: uppercase;
        letter-spacing: 1px; font-weight: 600; }}
  th:first-child, td:first-child, th:nth-child(3), td:nth-child(3),
  th:nth-child(4), td:nth-child(4) {{ text-align: left; }}
  td.name {{ font-weight: 600; }}
  td.ent {{ color: var(--muted); font-size: 11px; }}
  .tag {{ display: inline-block; padding: 2px 9px; border-radius: 999px;
          font-size: 11px; font-weight: 600; }}
  .tag.measured {{ background: rgba(62,207,142,.13); color: var(--low); }}
  .tag.estimated {{ background: rgba(242,178,45,.13); color: var(--medium); }}
  .tag.none {{ background: #232a35; color: var(--muted); }}
  td.eur {{ color: var(--low); }}
  tr.batt td.eur {{ color: var(--muted); }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">&#128268;</div>
    <div>
      <h1>Smart home energy</h1>
      <small>Per-device electricity usage &amp; cost &mdash; works without solar</small>
    </div>
  </header>

  <div class="card">
    <h2>Totals</h2>
    <div class="summary">
      <div><div class="label">Current power</div><div class="v" id="t-power">&hellip;</div></div>
      <div><div class="label">Today</div><div class="v" id="t-today-kwh">&hellip;</div></div>
      <div><div class="label">This month</div><div class="v" id="t-month-kwh">&hellip;</div></div>
      <div><div class="label">Today cost</div><div class="v eur" id="t-today-eur">&hellip;</div></div>
      <div><div class="label">Month cost</div><div class="v eur" id="t-month-eur">&hellip;</div></div>
    </div>
    <div class="muted" id="dev-note" style="margin-top:14px;font-size:12px;"></div>
  </div>

  <div class="card">
    <h2>Devices</h2>
    <table>
      <thead><tr>
        <th>Device</th><th>Entity</th><th>Type</th><th>Mode</th>
        <th>Power</th><th>Today kWh</th><th>Month kWh</th>
        <th>Today &euro;</th><th>Month &euro;</th>
      </tr></thead>
      <tbody id="rows"><tr><td colspan="9" class="muted">Loading&hellip;</td></tr></tbody>
    </table>
  </div>

  <footer><a href="./">&larr; Back to dashboard</a></footer>
</div>

<script>
const W = v => (v === null || v === undefined) ? '\\u2014'
  : (Math.abs(v) >= 1000 ? (v/1000).toFixed(2)+' kW' : Math.round(v)+' W');
const EUR = v => '\\u20ac ' + v.toFixed(2);
const KWH = v => v.toFixed(2);

async function load() {{
  const note = document.getElementById('dev-note');
  try {{
    const res = await fetch('api/devices');
    if (!res.ok) {{
      const b = await res.json().catch(() => ({{}}));
      note.textContent = b.detail || 'Devices unavailable.';
      return;
    }}
    const d = await res.json();
    document.getElementById('t-power').textContent = W(d.totals_current_power_w);
    document.getElementById('t-today-kwh').textContent = KWH(d.totals_today_kwh) + ' kWh';
    document.getElementById('t-month-kwh').textContent = KWH(d.totals_month_kwh) + ' kWh';
    document.getElementById('t-today-eur').textContent = EUR(d.totals_today_cost_eur);
    document.getElementById('t-month-eur').textContent = EUR(d.totals_month_cost_eur);

    const tbody = document.getElementById('rows');
    if (!d.devices.length) {{
      tbody.innerHTML = '<tr><td colspan="9" class="muted">No lights, switches, ' +
        'power, energy or battery entities found in Home Assistant.</td></tr>';
    }} else {{
      tbody.innerHTML = d.devices.map(u => {{
        const battClass = u.device_type === 'battery' ? ' class="batt"' : '';
        return `<tr${{battClass}}>
          <td class="name" title="${{u.note}}">${{u.name}}</td>
          <td class="ent">${{u.entity_id}}</td>
          <td>${{u.device_type.replace('_',' ')}}</td>
          <td><span class="tag ${{u.mode}}">${{u.mode}}</span></td>
          <td>${{W(u.current_power_w)}}</td>
          <td>${{KWH(u.today_kwh)}}</td>
          <td>${{KWH(u.month_kwh)}}</td>
          <td class="eur">${{EUR(u.today_cost_eur)}}</td>
          <td class="eur">${{EUR(u.month_cost_eur)}}</td>
        </tr>`;
      }}).join('');
    }}

    let info = d.device_count + ' devices (' + d.measured_count + ' measured, ' +
      d.estimated_count + ' estimated) \\u00b7 tariff \\u20ac ' +
      d.import_price_eur_per_kwh.toFixed(2) + '/kWh';
    info += d.measured_since
      ? ' \\u00b7 measured since ' + new Date(d.measured_since).toLocaleDateString()
      : ' \\u00b7 no history yet \\u2014 totals fill in as the add-on runs';
    note.textContent = info;
  }} catch (err) {{
    note.textContent = 'Failed to load devices: ' + err;
  }}
}}

load();
setInterval(load, 60000);
</script>
</body>
</html>
"""

SETTINGS_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar Brain &middot; Entity mapping</title>
<style>
{_BASE_CSS}
  .role-row {{ padding: 16px 0; border-bottom: 1px solid var(--border); }}
  .role-row:last-child {{ border-bottom: none; }}
  .role-name {{ font-size: 15px; font-weight: 600; }}
  .role-hint {{ color: var(--muted); font-size: 12px; margin: 2px 0 10px; }}
  select {{
    width: 100%; padding: 10px 12px; border-radius: 10px;
    background: #11151c; color: var(--text); border: 1px solid var(--border);
    font-size: 14px;
  }}
  .toolbar {{ display: flex; gap: 12px; align-items: center; margin-top: 20px; }}
  #status-msg {{ font-size: 13px; }}
  #status-msg.ok {{ color: var(--low); }}
  #status-msg.err {{ color: var(--high); }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">&#9881;</div>
    <div>
      <h1>Entity mapping</h1>
      <small>Tell Solar Brain which sensors to read</small>
    </div>
  </header>

  <div class="card">
    <h2>Sensor roles</h2>
    <div class="muted" id="conn-note" style="font-size:12px;margin-bottom:14px;"></div>
    <div id="roles">Loading entities from Home Assistant&hellip;</div>
    <div class="toolbar">
      <button class="btn" id="save-btn" disabled>Save mapping</button>
      <button class="btn secondary" id="autofill-btn" disabled>Auto-fill suggestions</button>
      <span id="status-msg"></span>
    </div>
  </div>

  <footer><a href="../">&larr; Back to dashboard</a></footer>
</div>

<script>
const ROLE_META = {{
  solar_power:       ['Solar production', 'Current PV output power (W or kW).'],
  battery_soc:       ['Battery state of charge', 'Battery level in %.'],
  grid_import_power: ['Grid import', 'Power currently drawn from the grid.'],
  grid_export_power: ['Grid export', 'Power currently fed into the grid.'],
  ev_power:          ['EV charging', 'Wallbox / EV charger power. Leave unmapped if you have none.'],
  home_load_power:   ['Home load', 'Total house consumption. Optional: computed from solar + import - export when unmapped.'],
}};

let discovery = null;

function option(entity, selected) {{
  const opt = document.createElement('option');
  opt.value = entity.entity_id;
  const state = entity.state !== '' ? ` \\u2022 ${{entity.state}} ${{entity.unit}}` : '';
  opt.textContent = `${{entity.name}} (${{entity.entity_id}})${{state}}`;
  opt.selected = selected;
  return opt;
}}

function buildRow(role) {{
  const [label, hint] = ROLE_META[role];
  const row = document.createElement('div');
  row.className = 'role-row';
  row.innerHTML = `<div class="role-name">${{label}}</div><div class="role-hint">${{hint}}</div>`;
  const select = document.createElement('select');
  select.id = 'sel-' + role;

  const none = document.createElement('option');
  none.value = '';
  none.textContent = '\\u2014 not mapped \\u2014';
  select.appendChild(none);

  const current = discovery.current_mapping[role] || '';
  const suggested = discovery.suggestions[role] || [];
  const suggestedIds = new Set(suggested.map(s => s.entity_id));

  if (suggested.length) {{
    const grp = document.createElement('optgroup');
    grp.label = 'Suggested';
    suggested.forEach(s => grp.appendChild(option(s, s.entity_id === current)));
    select.appendChild(grp);
  }}
  const rest = discovery.sensors.filter(s => !suggestedIds.has(s.entity_id));
  if (rest.length) {{
    const grp = document.createElement('optgroup');
    grp.label = 'All compatible sensors';
    rest.forEach(s => grp.appendChild(option(s, s.entity_id === current)));
    select.appendChild(grp);
  }}
  row.appendChild(select);
  return row;
}}

async function load() {{
  const container = document.getElementById('roles');
  const msg = document.getElementById('status-msg');
  try {{
    const res = await fetch('../api/entities/discover');
    if (!res.ok) {{
      const body = await res.json().catch(() => ({{}}));
      container.textContent = body.detail || 'Could not reach Home Assistant.';
      return;
    }}
    discovery = await res.json();
    container.innerHTML = '';
    Object.keys(ROLE_META).forEach(role => container.appendChild(buildRow(role)));
    document.getElementById('save-btn').disabled = false;
    document.getElementById('autofill-btn').disabled = false;
    if (discovery.connection) {{
      document.getElementById('conn-note').textContent =
        discovery.connection.message + ' (mode: ' + discovery.connection.mode +
        ', auth: ' + discovery.connection.auth.replace(/_/g, ' ') + ')';
    }}
  }} catch (err) {{
    container.textContent = 'Failed to load: ' + err;
  }}
}}

document.getElementById('autofill-btn').addEventListener('click', () => {{
  Object.keys(ROLE_META).forEach(role => {{
    const select = document.getElementById('sel-' + role);
    const top = (discovery.suggestions[role] || [])[0];
    if (select && top && !select.value) select.value = top.entity_id;
  }});
}});

document.getElementById('save-btn').addEventListener('click', async () => {{
  const msg = document.getElementById('status-msg');
  const mappings = {{}};
  Object.keys(ROLE_META).forEach(role => {{
    const select = document.getElementById('sel-' + role);
    mappings[role] = select.value || null;
  }});
  try {{
    const res = await fetch('../api/entities/mapping', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{mappings}}),
    }});
    const body = await res.json();
    if (res.ok) {{
      msg.className = 'ok';
      msg.textContent = 'Saved.';
    }} else {{
      msg.className = 'err';
      msg.textContent = body.detail || 'Save failed.';
    }}
  }} catch (err) {{
    msg.className = 'err';
    msg.textContent = 'Save failed: ' + err;
  }}
}});

load();
</script>
</body>
</html>
"""
