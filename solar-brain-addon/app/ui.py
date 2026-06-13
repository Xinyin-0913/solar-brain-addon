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

_NAV = (
    '<a href="./">Home</a> &middot; '
    '<a href="devices">Devices</a> &middot; '
    '<a href="settings/devices">Device profiles</a> &middot; '
    '<a href="settings/entities">Entity mapping</a> &middot; '
    '<a href="savings">Savings (solar)</a>'
)

DASHBOARD_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Home Energy</title>
<style>
{_BASE_CSS}
  .summary {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; }}
  .summary .v {{ font-size: 20px; font-weight: 700; }}
  .v.eur {{ color: var(--low); }}
  .counts {{ color: var(--muted); font-size: 12px; margin-top: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: right; padding: 8px 10px; border-bottom: 1px solid #232a35; }}
  th {{ color: var(--muted); font-size: 11px; text-transform: uppercase;
        letter-spacing: 1px; font-weight: 600; }}
  th:first-child, td:first-child, th:nth-child(2), td:nth-child(2),
  th:nth-child(3), td:nth-child(3) {{ text-align: left; }}
  td.name {{ font-weight: 600; }}
  .tag {{ display: inline-block; padding: 2px 9px; border-radius: 999px;
          font-size: 11px; font-weight: 600; }}
  .tag.measured {{ background: rgba(62,207,142,.13); color: var(--low); }}
  .tag.estimated {{ background: rgba(242,178,45,.13); color: var(--medium); }}
  .tag.monitoring, .tag.none {{ background: #232a35; color: var(--muted); }}
  td.eur {{ color: var(--low); }}
  .rec {{ display: flex; gap: 14px; align-items: flex-start; border-radius: 12px;
          padding: 14px 16px; }}
  .rec.info {{ background: rgba(24,188,242,.07); border: 1px solid rgba(24,188,242,.3); }}
  .rec.warning {{ background: rgba(242,178,45,.09); border: 1px solid rgba(242,178,45,.4); }}
  .rec .em {{ font-size: 22px; }}
  .rec b {{ display: block; font-size: 15px; margin-bottom: 3px; }}
  .rec span {{ font-size: 13px; color: var(--muted); line-height: 1.5; }}
  .solar-small {{ font-size: 13.5px; color: var(--muted); line-height: 1.6; }}
  .solar-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">&#9889;</div>
    <div>
      <h1>Smart Home Energy</h1>
      <small>Smart home energy management for Home Assistant</small>
    </div>
  </header>

  <div class="card">
    <h2>Home energy summary</h2>
    <div class="summary">
      <div><div class="label">Current power</div><div class="v" id="s-power">&hellip;</div></div>
      <div><div class="label">Today</div><div class="v" id="s-today-kwh">&hellip;</div></div>
      <div><div class="label">This month</div><div class="v" id="s-month-kwh">&hellip;</div></div>
      <div><div class="label">Today cost</div><div class="v eur" id="s-today-eur">&hellip;</div></div>
      <div><div class="label">Month cost</div><div class="v eur" id="s-month-eur">&hellip;</div></div>
    </div>
    <div class="counts" id="s-counts"></div>
  </div>

  <div class="card">
    <h2>Smart home recommendation</h2>
    <div class="rec info" id="rec"><span class="em">&#8505;</span>
      <div><b id="rec-text">&hellip;</b><span id="rec-detail"></span></div>
    </div>
  </div>

  <div class="card">
    <h2>Top devices</h2>
    <table>
      <thead><tr>
        <th>Device</th><th>Type</th><th>Mode</th><th>Power</th>
        <th>Today kWh</th><th>Month kWh</th><th>Today &euro;</th><th>Month &euro;</th>
      </tr></thead>
      <tbody id="rows"><tr><td colspan="8" class="muted">Loading&hellip;</td></tr></tbody>
    </table>
    <div style="margin-top:12px;font-size:12px;"><a href="devices">See all devices &rarr;</a></div>
  </div>

  <div class="card" id="solar-card">
    <h2>Solar / PV module</h2>
    <div id="solar-body" class="solar-small">Checking&hellip;</div>
  </div>

  <footer>{_NAV}</footer>
</div>

<script>
const W = v => (v === null || v === undefined) ? '\\u2014'
  : (Math.abs(v) >= 1000 ? (v/1000).toFixed(2)+' kW' : Math.round(v)+' W');
const EUR = v => '\\u20ac ' + (v || 0).toFixed(2);
const KWH = v => (v || 0).toFixed(2) + ' kWh';
const PV_ROLES = ['solar_power','battery_soc','grid_import_power','grid_export_power','ev_power'];

async function loadHome() {{
  const counts = document.getElementById('s-counts');
  try {{
    const res = await fetch('api/devices');
    if (!res.ok) {{
      const b = await res.json().catch(() => ({{}}));
      counts.textContent = b.detail || 'Devices unavailable.';
      return;
    }}
    const d = await res.json();
    document.getElementById('s-power').textContent = W(d.totals_current_power_w);
    document.getElementById('s-today-kwh').textContent = KWH(d.totals_today_kwh);
    document.getElementById('s-month-kwh').textContent = KWH(d.totals_month_kwh);
    document.getElementById('s-today-eur').textContent = EUR(d.totals_today_cost_eur);
    document.getElementById('s-month-eur').textContent = EUR(d.totals_month_cost_eur);
    let info = d.device_count + ' devices discovered \\u00b7 ' + d.measured_count +
      ' measured \\u00b7 ' + d.estimated_count + ' estimated \\u00b7 tariff \\u20ac ' +
      d.import_price_eur_per_kwh.toFixed(2) + '/kWh';
    info += d.measured_since
      ? ' \\u00b7 totals since ' + new Date(d.measured_since).toLocaleDateString() +
        ' (when data collection started)'
      : ' \\u00b7 collecting data \\u2014 totals fill in as the add-on runs';
    counts.textContent = info;

    const tbody = document.getElementById('rows');
    const top = d.devices.slice(0, 10);
    tbody.innerHTML = top.length ? top.map(u => `<tr>
      <td class="name" title="${{u.note}}">${{u.name}}</td>
      <td>${{(u.appliance_type || u.device_type).replace(/_/g,' ')}}</td>
      <td><span class="tag ${{u.mode}}">${{u.mode}}</span></td>
      <td>${{W(u.current_power_w)}}</td>
      <td>${{KWH(u.today_kwh)}}</td><td>${{KWH(u.month_kwh)}}</td>
      <td class="eur">${{EUR(u.today_cost_eur)}}</td>
      <td class="eur">${{EUR(u.month_cost_eur)}}</td></tr>`).join('')
      : '<tr><td colspan="8" class="muted">No devices found. Add lights, switches ' +
        'or power sensors in Home Assistant.</td></tr>';
  }} catch (err) {{ counts.textContent = 'Failed to load: ' + err; }}
}}

async function loadRecommendation() {{
  try {{
    const res = await fetch('api/home/recommendation');
    if (!res.ok) return;
    const r = await res.json();
    document.getElementById('rec').className = 'rec ' + r.severity;
    document.getElementById('rec-text').textContent = r.text;
    const detail = document.getElementById('rec-detail');
    detail.textContent = r.detail || '';
    if (r.action_url) {{
      detail.innerHTML += ' <a href="' + r.action_url + '">Configure &rarr;</a>';
    }}
  }} catch (err) {{ /* leave default */ }}
}}

async function loadSolar() {{
  const body = document.getElementById('solar-body');
  try {{
    const m = await fetch('api/entities/mapping').then(r => r.json());
    const mapped = PV_ROLES.filter(role => m.mappings && m.mappings[role]);
    if (!mapped.length) {{
      body.innerHTML = 'Solar module not configured. ' +
        '<a href="settings/entities">Map solar / grid / battery entities</a> if you have a PV system.';
      return;
    }}
    const t = await fetch('api/telemetry/current').then(r => r.json());
    body.innerHTML = '<div class="solar-grid">' +
      '<div><div class="label">Solar</div><div class="value">' + W(t.solar_power_w) + '</div></div>' +
      '<div><div class="label">Battery</div><div class="value">' +
        (t.battery_soc === null ? '\\u2014' : t.battery_soc.toFixed(0)+' %') + '</div></div>' +
      '<div><div class="label">Grid import</div><div class="value">' + W(t.grid_import_w) + '</div></div>' +
      '<div><div class="label">Grid export</div><div class="value">' + W(t.grid_export_w) + '</div></div>' +
      '</div><div style="margin-top:12px"><a href="savings">Solar savings details &rarr;</a></div>';
  }} catch (err) {{
    body.textContent = 'Solar module not configured.';
  }}
}}

function loadAll() {{ loadHome(); loadRecommendation(); loadSolar(); }}
loadAll();
setInterval(loadAll, 60000);
</script>
</body>
</html>
"""

SAVINGS_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Home Energy &middot; Savings (solar)</title>
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

  <footer>{_NAV}</footer>
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
<title>Smart Home Energy &middot; Devices</title>
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

  <footer>{_NAV}</footer>
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

DEVICE_PROFILES_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Home Energy &middot; Device profiles</title>
<style>
{_BASE_CSS}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 9px 8px; border-bottom: 1px solid #232a35;
            vertical-align: middle; }}
  th {{ color: var(--muted); font-size: 11px; text-transform: uppercase;
        letter-spacing: 1px; font-weight: 600; }}
  td.ent {{ color: var(--muted); font-size: 11px; }}
  input, select {{ background: #11151c; color: var(--text); border: 1px solid var(--border);
                   border-radius: 8px; padding: 7px 9px; font-size: 13px; font-family: inherit; }}
  input.name {{ width: 150px; }} input.watt {{ width: 80px; }}
  .toolbar {{ display: flex; gap: 12px; align-items: center; margin-top: 20px; }}
  .btn {{ background: var(--accent); color: #14171c; border: none; cursor: pointer;
          padding: 10px 22px; border-radius: 10px; font-size: 14px; font-weight: 700; }}
  #msg {{ font-size: 13px; }} #msg.ok {{ color: var(--low); }} #msg.err {{ color: var(--high); }}
  .hint {{ color: var(--muted); font-size: 12.5px; line-height: 1.6; margin-bottom: 16px; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">&#9881;</div>
    <div>
      <h1>Device profiles</h1>
      <small>Set rated power for smart plugs &amp; lights so estimates are accurate</small>
    </div>
  </header>

  <div class="card">
    <h2>Controllable devices</h2>
    <div class="hint">
      For devices with no power sensor, energy is estimated as
      <b>rated power &times; on-time</b>. Set the real wattage of what each smart
      plug controls (e.g. a heater vs a phone charger). Devices that report their
      own power are measured automatically and ignore these settings.
      Leave rated power blank to use the default for the device type.
    </div>
    <table>
      <thead><tr>
        <th>Entity</th><th>Display name</th><th>Appliance type</th>
        <th>Rated power (W)</th><th>Estimate?</th>
      </tr></thead>
      <tbody id="rows"><tr><td colspan="5" class="muted">Loading&hellip;</td></tr></tbody>
    </table>
    <div class="toolbar">
      <button class="btn" id="save" disabled>Save profiles</button>
      <span id="msg"></span>
    </div>
  </div>

  <footer><a href="../">&larr; Back to home</a></footer>
</div>

<script>
let applianceTypes = [];

async function load() {{
  const tbody = document.getElementById('rows');
  try {{
    const res = await fetch('../api/devices/profiles');
    if (!res.ok) {{
      const b = await res.json().catch(() => ({{}}));
      tbody.innerHTML = '<tr><td colspan="5" class="muted">' +
        (b.detail || 'Unavailable.') + '</td></tr>';
      return;
    }}
    const d = await res.json();
    applianceTypes = d.appliance_types;
    const devs = d.controllable_devices;
    if (!devs.length) {{
      tbody.innerHTML = '<tr><td colspan="5" class="muted">No lights or switches ' +
        'found in Home Assistant.</td></tr>';
      return;
    }}
    tbody.innerHTML = devs.map(dev => {{
      const p = d.profiles[dev.entity_id] || {{}};
      const selType = p.appliance_type || dev.appliance_type || 'custom';
      const opts = applianceTypes.map(t =>
        `<option value="${{t}}"${{selType === t ? ' selected' : ''}}>` +
        t.replace(/_/g,' ') + '</option>').join('');
      const measured = dev.mode === 'measured';
      return `<tr data-entity="${{dev.entity_id}}" data-measured="${{measured}}">
        <td class="ent">${{dev.entity_id}}${{measured ? ' \\u2022 measured' : ''}}</td>
        <td><input class="name" value="${{p.display_name || ''}}" placeholder="${{dev.name}}"></td>
        <td><select class="atype">${{opts}}</select></td>
        <td><input class="watt" type="number" min="0" step="1"
             value="${{p.rated_power_w ?? ''}}" placeholder="${{dev.estimated_wattage ?? ''}}"
             ${{measured ? 'disabled' : ''}}></td>
        <td><input class="est" type="checkbox" ${{p.estimation_enabled === false ? '' : 'checked'}}></td>
      </tr>`;
    }}).join('');
    document.getElementById('save').disabled = false;
  }} catch (err) {{
    tbody.innerHTML = '<tr><td colspan="5" class="muted">Failed: ' + err + '</td></tr>';
  }}
}}

document.getElementById('save').addEventListener('click', async () => {{
  const msg = document.getElementById('msg');
  const profiles = [...document.querySelectorAll('#rows tr[data-entity]')].map(tr => {{
    const watt = tr.querySelector('.watt').value;
    const name = tr.querySelector('.name').value.trim();
    return {{
      entity_id: tr.dataset.entity,
      display_name: name || null,
      appliance_type: tr.querySelector('.atype').value,
      rated_power_w: watt === '' ? null : parseFloat(watt),
      estimation_enabled: tr.querySelector('.est').checked,
    }};
  }});
  try {{
    const res = await fetch('../api/devices/profiles', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{profiles}}),
    }});
    const b = await res.json();
    msg.className = res.ok ? 'ok' : 'err';
    msg.textContent = res.ok ? ('Saved ' + b.saved + ' profiles.') : (b.detail || 'Failed.');
  }} catch (err) {{ msg.className = 'err'; msg.textContent = 'Failed: ' + err; }}
}});

load();
</script>
</body>
</html>
"""

SETTINGS_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Home Energy &middot; Entity mapping</title>
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
      <small>Map solar / grid / battery / EV sensors (optional PV module)</small>
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

  <footer><a href="../">&larr; Back to home</a></footer>
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
