# 34 — Topology & Live Monitor Pages

---

## PART A — Topology Page (`/topology/`)

**Template:** `fl_shap_dashboard/templates/pages/topology.html`  
**View:** `views.py → def topology()`  
**URL:** `/topology/`  
**Note:** This page does NOT extend `base.html` — it is a fully standalone HTML document with its own CSS file (`static/css/topology.css`) and 5 separate JS component files.

---

### A1. Django View Function

```python
@login_required
def topology(request):
    factories  = api_client.get_factories()
    metrics    = api_client.get_metrics()
    clusters   = api_client.get_clusters()
    history    = api_client.get_cluster_history()
    all_rounds = api_client.get_rounds(limit=500)

    # ── Build per-round weighted accuracy for chart ──
    round_data = {}
    for r in all_rounds:
        rn = r['round_num']
        round_data.setdefault(rn, []).append(r)

    chart_data = []
    for rn in sorted(round_data.keys()):
        rlist = round_data[rn]
        total = sum(r['n_samples'] for r in rlist)
        avg   = sum(r['accuracy'] * r['n_samples'] for r in rlist) / total if total > 0 else 0
        chart_data.append({'round': rn, 'accuracy': round(avg, 4)})

    latest_acc  = chart_data[-1]['accuracy'] if chart_data else None
    total_nodes = sum(len(v) for k, v in clusters.items())
    n_clusters  = len([k for k in clusters if k != 'unassigned'])
    latest_round_num = max(round_data.keys(), default=0) if round_data else 0

    # ── Build recent events from cluster history ──
    events = []
    for h in reversed((history or [])[-8:]):
        events.append({
            'text':       f"Cluster {h.get('cluster_id','?')} updated — round {h.get('round_num','?')}",
            'cluster_id': h.get('cluster_id'),
            'timestamp':  h.get('timestamp'),
        })

    context = {
        'ws_url':           'ws://localhost:8000/ws',
        'clusters_json':    json.dumps(clusters),
        'metrics_json':     json.dumps(metrics),
        'chart_data_json':  json.dumps(chart_data),
        'events_json':      json.dumps(events),
        'sim_info_json':    json.dumps({
            'round':        latest_round_num,
            'total_rounds': metrics.get('total_rounds', 500),
            'nodes':        total_nodes,
            'clusters':     n_clusters,
            'accuracy':     latest_acc,
            'convergence':  metrics.get('convergence_rate'),
            'status':       'Running',
        }),
    }
    return render(request, 'pages/topology.html', context)
```

**Weighted accuracy formula:**
```
avg = Σ(accuracy_i × n_samples_i) / Σ(n_samples_i)
```
Each round has 4 rows (one per factory). Factories with more training samples contribute proportionally more to the round average.

**`get_clusters()` returns:** A dict mapping cluster IDs to lists of factory IDs:
```json
{ "0": [1, 3], "1": [2, 4], "unassigned": [] }
```

---

### A2. Data Injection (lines 96–104)

The entire dataset is injected as a single `TOPO_DATA` JavaScript object:

```html
<script>
const TOPO_DATA = {
  clusters:  {{ clusters_json   | safe }},   // cluster→factories dict
  metrics:   {{ metrics_json    | safe }},   // {total_rounds, active_factories, ...}
  chartData: {{ chart_data_json | safe }},   // [{round:1, accuracy:0.62}, ...]
  events:    {{ events_json     | safe }},   // [{text, cluster_id, timestamp}, ...]
  simInfo:   {{ sim_info_json   | safe }},   // {round, total_rounds, nodes, clusters, ...}
  wsUrl:     "{{ ws_url }}",                 // "ws://localhost:8000/ws"
};
</script>
```

`| safe` filter — tells Django to skip HTML escaping, since these are JSON strings that need to be valid JavaScript.

---

### A3. Three-Column Layout

```
┌──────────────────────────────────────────────────────────────────┐
│                         TOP BAR                                  │
├──────────┬─────────────────────────────────┬────────────────────┤
│  LEFT    │    MAIN CANVAS (topo-canvas)    │  RIGHT PANEL       │
│ SIDEBAR  │    Canvas controls (zoom/fit)   │  (topo-panel)      │
│(topo-    │    Node tooltip                 │                    │
│ sidebar) │                                 │                    │
└──────────┴─────────────────────────────────┴────────────────────┘
```

All three regions start as empty `<div>` elements — content is injected by JS component files:

| Region | Element ID | JS Component | What it renders |
|--------|-----------|--------------|-----------------|
| Left sidebar | `topo-sidebar` | `Sidebar.js` | Sim info (round, nodes, accuracy, status) |
| Main canvas | `topo-canvas` | `ClusterGraph.js` | Interactive cluster graph with factory nodes |
| Right panel | `topo-panel` | `MetricsPanel.js` | Accuracy chart + cluster breakdown + event list |

---

### A4. JavaScript Component Architecture

5 external JS files loaded from `static/js/`:

```javascript
// 1. Renders left sidebar with sim info
Sidebar.render(document.getElementById('topo-sidebar'), TOPO_DATA.simInfo, 'topology');

// 2. Renders right panel (accuracy chart + cluster details + event list)
MetricsPanel.render(document.getElementById('topo-panel'), {
  chartData: TOPO_DATA.chartData,
  metrics:   TOPO_DATA.metrics,
  clusters:  TOPO_DATA.clusters,
  events:    TOPO_DATA.events,
});

// 3. Renders the interactive cluster graph on the canvas
const graph = new ClusterGraph(canvas, tooltip, TOPO_DATA.clusters);
```

**Zoom controls (lines 129–136):**
```javascript
let zoom = 100;
function updateZoom(delta) {
  zoom = Math.max(50, Math.min(200, zoom + delta));  // clamp 50–200%
  document.getElementById('zoom-label').textContent = zoom + '%';
}
document.getElementById('ctrl-zoom-in') .addEventListener('click', () => updateZoom(+10));
document.getElementById('ctrl-zoom-out').addEventListener('click', () => updateZoom(-10));
document.getElementById('ctrl-fit')     .addEventListener('click', () => { zoom = 100; updateZoom(0); });
```

**WebSocket listener (lines 139–150):**
```javascript
const ws = new WebSocket(TOPO_DATA.wsUrl);
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'training_round' && msg.data) {
    const siRound = document.getElementById('si-round');
    if (siRound) siRound.textContent = `${msg.data.round_num}/${TOPO_DATA.simInfo.total_rounds}`;
  }
};
```
Only handles `training_round` event to update the round counter in the sidebar. The entire topology graph is server-rendered — it does not update live during training.

---

---

## PART B — Live Monitor Page (`/monitor/`)

**Template:** `fl_shap_dashboard/templates/pages/monitor.html`  
**View:** `views.py → def monitor()` and `def monitor_api()`  
**URLs:** `/monitor/` (page), `/api/monitor/` (JSON polling endpoint)

---

### B1. Django View Functions

**Shell view (renders the page, no data):**
```python
@login_required
def monitor(request):
    return render(request, 'pages/monitor.html', {'active_page': 'monitor'})
```

**JSON polling endpoint (called by JS every N seconds):**
```python
@login_required
def monitor_api(request):
    factory_id = int(request.GET.get('factory_id', random.randint(1, 4)))
    try:
        resp = requests.post(
            "http://localhost:8001/explain/demo",
            params={"factory_id": factory_id, "scenario": "random"},
            timeout=12,
        )
        if resp.status_code == 200:
            data = resp.json()
            data['confidence'] = round(data.get('confidence', 0) * 100, 1)
            data['factory_id'] = factory_id
            return JsonResponse({'ok': True, 'data': data})
        return JsonResponse({'ok': False, 'error': f'SHAP API returned {resp.status_code}'})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})
```

`monitor_api` calls the SHAP API directly and returns JSON. The browser JS polls this endpoint rather than calling SHAP directly (keeps SHAP API hidden from the browser).

---

### B2. Controls Bar (lines 22–78)

Four live controls:

| Control | Element ID | `onchange` handler | Effect |
|---------|-----------|-------------------|--------|
| Interval picker | `interval-select` | `changeInterval()` | Changes polling frequency (5/10/20/30s) |
| Factory filter | `factory-select` | `changeInterval()` | Restricts which factory's engines are sampled |
| Pause/Resume | `pause-btn` | `togglePause()` | Stops/starts the polling loop |
| Live stats | `total-count`, `correct-count`, `accuracy-pct`, `failure-count` | Updated by `updateUI()` | Running totals |

---

### B3. Current Prediction Panel (lines 100–170)

A 2-column panel that updates every N seconds with a fresh prediction:

**Left column — AI Prediction:**
- `id="panel-header"` — background turns coral (FAILURE) or indigo (HEALTHY)
- `id="panel-title"` — `"Engine #47 — test_FD001.txt · Cycles 82–111"`
- `id="pred-label"` — `"FAILURE"` or `"HEALTHY"` in large font
- `id="pred-confidence"` — `"81.2%"`
- `id="pred-detail"` — explanatory sentence

**Right column — Actual Ground Truth:**
- `id="actual-label"` — `"FAILURE"` or `"HEALTHY"`
- `id="actual-rul"` — `"18 cycles remaining"`
- `id="actual-panel"` — background: green-bg (match) or coral-bg (mismatch)

**Trace bar (5 columns):**
- `trace-dataset`, `trace-engine`, `trace-cycles`, `trace-total`, `trace-sensors`

---

### B4. Core JavaScript Functions

**Global state variables:**
```javascript
let paused       = false;
let intervalMs   = 10000;   // default: 10 seconds
let timerId      = null;    // setTimeout ID for next poll
let countdownTimer = null;  // setInterval ID for countdown bar
let secondsLeft  = 10;
let totalCount   = 0;       // running stats
let correctCount = 0;
let failureCount = 0;
let logRows      = [];      // ring buffer: last 15 predictions
```

**`getFactoryId()`**
```javascript
function getFactoryId() {
  const v = parseInt(document.getElementById('factory-select').value);
  if (v === 0) return Math.floor(Math.random() * 4) + 1;  // random 1–4
  return v;   // specific factory selected
}
```

**`fetchPrediction()`** — the main poll function:
```javascript
async function fetchPrediction() {
  if (paused) return;
  const fid = getFactoryId();
  const resp = await fetch(`/api/monitor/?factory_id=${fid}`);
  const json = await resp.json();
  if (json.ok) updateUI(json.data);
}
```
Calls Django's `/api/monitor/` endpoint (not SHAP directly). Returns `{ok, data}`.

**`updateUI(d)`** — updates every DOM element and stats counter:
```javascript
function updateUI(d) {
  const isFailure = d.prediction === 'FAILURE';
  const isMatch   = d.prediction === d.actual_label;

  // Panel header color
  document.getElementById('panel-header').style.background =
    isFailure ? 'var(--coral)' : '#5B6BDF';

  // All text updates...
  document.getElementById('pred-label').textContent     = isFailure ? 'FAILURE' : 'HEALTHY';
  document.getElementById('pred-confidence').textContent = `${d.confidence}%`;
  document.getElementById('actual-rul').textContent     = `${d.actual_rul} cycles remaining`;
  document.getElementById('actual-panel').style.background =
    isMatch ? 'var(--green-bg)' : 'var(--coral-bg)';

  // Failure alert banner
  if (isFailure) {
    document.getElementById('alert-banner').style.display = 'block';
    // Status dot → red pulse for 5 seconds, then back to green
    const dot = document.getElementById('status-dot');
    dot.style.animation = 'pulse-red 0.8s ease-in-out infinite';
    setTimeout(() => { dot.style.animation = 'pulse-green 1.5s ease-in-out infinite'; }, 5000);
  }

  // Running stats
  totalCount++;
  if (isMatch) correctCount++;
  if (isFailure) failureCount++;
  document.getElementById('accuracy-pct').textContent =
    totalCount > 0 ? `${Math.round((correctCount/totalCount)*100)}%` : '—';

  // Log ring buffer
  logRows.unshift({ ts, d, isMatch, isFailure });
  if (logRows.length > 15) logRows.pop();
  renderLog();
}
```

**`renderLog()`** — re-renders the full log table from `logRows` array:
```javascript
function renderLog() {
  document.getElementById('log-body').innerHTML = logRows.map((r, i) => `
    <div class="log-row" style="display:grid; grid-template-columns:80px 1fr 100px 100px 100px 100px 70px;
      background:${i === 0 ? 'rgba(91,107,223,0.06)' : (i%2===0 ? 'var(--bg)' : 'var(--card)')};
      ...">
      <span>${r.ts}</span>
      <span>${r.d.dataset_file} Engine #${r.d.engine_id}</span>
      <span>${r.d.start_cycle}–${r.d.end_cycle}</span>
      <span style="color:${predColor}">${r.d.prediction}</span>
      <span style="color:${actColor}">${r.d.actual_label}</span>
      <span>${r.d.actual_rul} cycles</span>
      <span style="color:${matchFg}">${r.isMatch ? 'OK' : 'NO'}</span>
    </div>`
  ).join('');
}
```
- `logRows[0]` (newest) gets a blue-tinted `rgba(91,107,223,0.06)` background + CSS `highlight-in` animation
- Even rows: `var(--bg)`, odd rows: `var(--card)` — zebra striping

**`startCountdown()`** — animates the progress bar below the log:
```javascript
function startCountdown() {
  const bar = document.getElementById('countdown-bar');
  bar.style.transition = 'none';
  bar.style.width = '100%';      // reset to full
  setTimeout(() => {
    bar.style.transition = `width ${intervalMs/1000}s linear`;
    bar.style.width = '0%';      // drain to zero over intervalMs seconds
  }, 50);
  // Countdown text: 10s, 9s, 8s...
  countdownTimer = setInterval(() => {
    if (!paused) { secondsLeft--; txt.textContent = secondsLeft + 's'; }
  }, 1000);
}
```

**`scheduleNext()`** — recursive timeout loop:
```javascript
function scheduleNext() {
  startCountdown();
  timerId = setTimeout(async () => {
    await fetchPrediction();
    scheduleNext();       // reschedule after each prediction
  }, intervalMs);
}
```

**`togglePause()`** — pauses/resumes the loop:
```javascript
function togglePause() {
  paused = !paused;
  if (paused) {
    clearTimeout(timerId);
    clearInterval(countdownTimer);
    btn.textContent = '▶ RESUME';
    statusDot.style.animation = 'none';
  } else {
    scheduleNext();   // restart loop
    btn.textContent = '⏸ PAUSE';
  }
}
```

**Boot sequence (lines 447–451):**
```javascript
(async () => {
  await fetchPrediction();   // fire immediately on page load (no waiting)
  scheduleNext();            // start the recurring loop
})();
```

---

### B5. CSS Animations (defined inline in `{% block extra_scripts %}`)

```css
@keyframes pulse-green {
  0%   { box-shadow: 0 0 0 0 rgba(20,107,58,0.6); }
  70%  { box-shadow: 0 0 0 8px rgba(20,107,58,0); }
  100% { box-shadow: 0 0 0 0 rgba(20,107,58,0); }
}
@keyframes pulse-red {
  0%   { box-shadow: 0 0 0 0 rgba(232,82,26,0.6); }
  70%  { box-shadow: 0 0 0 8px rgba(232,82,26,0); }
}
@keyframes flash-border {    /* failure alert banner flashing border */
  from { border-color: #c0390a; }
  to   { border-color: rgba(232,82,26,0.3); }
}
@keyframes highlight-in {    /* newest log row flash */
  from { background: rgba(91,107,223,0.12); }
  to   { background: transparent; }
}
```

---

### B6. Full Monitor Page Polling Loop

```
Page loads → boot IIFE fires:
    ↓
fetchPrediction() → GET /api/monitor/?factory_id=3
    ↓
views.monitor_api() → POST http://localhost:8001/explain/demo?factory_id=3&scenario=random
    ↓
SHAP API → picks random engine from test_FD003.txt
    ↓
Returns SHAPResponse → monitor_api wraps in {ok:true, data:{...}}
    ↓
updateUI(d) fires:
  - Updates panel header color, engine title, prediction label
  - Updates actual label + RUL
  - Updates trace bar (dataset, engine ID, cycles)
  - If FAILURE → shows alert banner + red dot pulse (resets after 5s)
  - Increments totalCount, correctCount/failureCount
  - Prepends to logRows[], calls renderLog()
    ↓
scheduleNext() starts countdown bar animation
    ↓
After intervalMs (default 10s):
  fetchPrediction() fires again → loop repeats
```
