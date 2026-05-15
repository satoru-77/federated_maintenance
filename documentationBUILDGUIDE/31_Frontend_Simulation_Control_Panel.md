# 31 — Simulation Control Panel Page

**Template:** `fl_shap_dashboard/templates/pages/simulation.html`  
**View:** `views.py → def simulation()`  
**URL:** `/simulation/`  
**Purpose:** Operator control panel — start/stop FL training, inject attack scenarios, monitor live WebSocket events

---

## 1. Django View Function (`def simulation()`)

**Location:** `views.py` line 78

```python
@login_required
def simulation(request):
    factories = api_client.get_factories()   # GET /factories from FastAPI
    metrics   = api_client.get_metrics()     # GET /metrics from FastAPI
    return render(request, 'pages/simulation.html', {
        'factories':   factories,   # list of 4 factory dicts
        'metrics':     metrics,     # {total_rounds, active_factories, latest_round_num, ...}
        'ws_url':      'ws://localhost:8000/ws',
        'active_page': 'simulation',
    })
```

Minimal view — no heavy processing. The page is mostly driven by JS + WebSocket. The factory list and metrics are only used for the initial server-rendered state; JavaScript updates them live via WS.

---

## 2. Page Header (lines 7–26)

```html
<div style="border-bottom:1.5px solid var(--border); padding-bottom:24px; margin-bottom:32px;
            display:flex; align-items:flex-end; justify-content:space-between;">
  <div>
    <span class="tag-label">[ FEDERATED CONTROL PANEL ]</span>
    <h1 class="font-display" style="font-size:2.4rem; font-weight:800;">Simulation</h1>
    <p style="font-family:'DM Mono'; font-size:11px; color:var(--muted);">
      Training control · scenario injection · live event stream
    </p>
  </div>
  <!-- Live WebSocket indicator (top-right) -->
  <div style="display:flex; align-items:center; gap:6px; background:var(--green-bg);
              border:1px solid var(--green-lt); padding:6px 14px;">
    <div class="live-dot"></div>   <!-- pulsing green dot from base.html CSS -->
    <span style="font-size:10px; color:var(--green-2); letter-spacing:0.1em;">WEBSOCKET LIVE</span>
  </div>
</div>
```

The `.live-dot` CSS animation is defined in `base.html`:
```css
.live-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #4ADE80;
  animation: live-pulse 1.6s ease-in-out infinite;
}
@keyframes live-pulse {
  0%,100% { opacity:1; transform:scale(1); }
  50%      { opacity:.4; transform:scale(.85); }
}
```

---

## 3. Startup Instructions Banner (lines 29–43)

```html
<div style="background:var(--cream-2); border:1.5px solid var(--border);
            padding:14px 20px; margin-bottom:28px;
            display:flex; align-items:center; justify-content:space-between;">
  <div>
    <span style="color:var(--green-2); font-size:9px; font-weight:700;">HOW TO START TRAINING</span>
    <p style="font-size:12px; color:var(--ink); margin:5px 0 0; line-height:1.6;">
      Run <code>.\start_fl.ps1</code> from <code>fl_backend/</code>
      in PowerShell — launches the Flower server and all 4 factory clients.
    </p>
  </div>
  <code style="background:var(--ink); color:#4ADE80; padding:8px 16px; font-size:10px;">
    .\start_fl.ps1
  </code>
</div>
```

Static informational panel. No interactivity.

---

## 4. Main Grid: Left Panel (Event Log + Factory Status)

Main layout is `grid-template-columns: 3fr 1fr` — left takes 75% width, right 25%.

### 4a. Factory Node Status (lines 52–71)

Renders each factory as a row using the `factories` context variable:

```html
{% for f in factories %}
<div style="display:flex; align-items:center; gap:16px; padding:11px 16px;
  {% if not forloop.last %}border-bottom:1px solid var(--border-2);{% endif %}">

  <!-- Colored circle dot (hardcoded per position in loop) -->
  <div style="width:7px; height:7px; border-radius:50%; background:
    {% if forloop.counter0 == 0 %}var(--green)
    {% elif forloop.counter0 == 1 %}var(--coral)
    {% elif forloop.counter0 == 2 %}#2563EB
    {% else %}#7C3AED{% endif %};">
  </div>

  <span class="font-display" style="font-weight:700; font-size:13px; min-width:140px;">
    {{ f.name }}         <!-- "Factory Mumbai" -->
  </span>

  <span style="font-size:10px; color:var(--muted); flex:1;">
    {{ f.dataset }}      <!-- "FD001" -->
  </span>

  <!-- Cluster badge — updated via WebSocket -->
  <span id="sim-badge-{{ f.factory_id }}" class="badge-cluster-{{ f.cluster_id|default:0 }}">
    {{ f.cluster_label }}  <!-- "Unassigned" or "Cluster 0" -->
  </span>

  <span style="font-size:9px; color:var(--green-2);">ACTIVE</span>
</div>
{% endfor %}
```

The `id="sim-badge-{{ f.factory_id }}"` (e.g. `sim-badge-1`) is targeted by the WebSocket listener to update the badge when a `cluster_assigned` event fires.

**`forloop.counter0`** is Django's zero-indexed loop counter — used here to map loop position to a dot color without needing the actual `factory_id`.

### 4b. Stat Mini-Cards (lines 73–87)

3-column grid with live-updating numbers:

```html
<div style="display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:var(--border);">

  <div style="background:var(--bg); padding:16px 14px;">
    <span style="font-size:8px; color:var(--muted);">TOTAL ROUNDS</span>
    <div id="sim-total-rounds" class="font-display" style="font-weight:800; font-size:1.8rem;">
      {{ metrics.total_rounds|default:"—" }}   <!-- server-rendered initial value -->
    </div>
  </div>

  <div style="background:var(--bg); padding:16px 14px; border-left:1px solid var(--border);">
    <span>ACTIVE CLIENTS</span>
    <div id="sim-active-clients" ...>{{ metrics.active_factories|default:"—" }}</div>
  </div>

  <div style="background:var(--bg); padding:16px 14px; border-left:1px solid var(--border);">
    <span>LATEST ROUND</span>
    <div id="sim-latest-round" ...>{{ metrics.latest_round_num|default:"—" }}</div>
  </div>

</div>
```

IDs `sim-total-rounds`, `sim-active-clients`, `sim-latest-round` are updated by JS WebSocket handler.

### 4c. Live Event Log Terminal (lines 89–102)

A dark terminal-style div that receives appended lines:

```html
<div id="sim-log" style="background:#0d1117; border:1.5px solid #30363d;
  padding:16px 18px; height:260px; overflow-y:auto;
  font-family:'DM Mono'; font-size:11px; color:#8b949e; line-height:1.9;">
  <span style="color:#3d454f;">-- waiting for events --</span><br>
  <span style="color:#3d454f;">-- WebSocket: ws://localhost:8000/ws --</span><br>
</div>
```

Initial content is static placeholder text. New lines are prepended by `addSimLog()` and the log auto-scrolls. Color scheme: GitHub dark theme (`#0d1117` bg, `#30363d` border).

---

## 5. Right Panel: System Controls (lines 106–168)

### 5a. Start / Stop Buttons (lines 113–126)

```html
<button id="start-btn" class="btn-primary" style="width:100%; ...">
  <span>Start Simulation</span>
  <span style="font-size:8px; opacity:0.5;">/sim/start</span>
</button>

<button id="stop-btn" style="width:100%; background:transparent;
  border:1.5px solid var(--coral-lt); color:var(--coral); ...">
  <span>Stop & Kill Terminals</span>
  <span style="font-size:8px; opacity:0.5;">/sim/stop</span>
</button>
```

### 5b. Scenario Injection Dropdown (lines 132–145)

```html
<select id="scenario-select" class="fl-select" style="width:100%; margin-bottom:10px;">
  <option value="">-- select scenario --</option>
  <option value="byzantine">Simulate Byzantine Attack</option>
  <option value="recluster">Trigger Re-clustering (k=3)</option>
  <option value="new_factory">Add New Factory</option>
  <option value="drop_factory">Drop Factory Client</option>
</select>
<button class="btn-coral" style="width:100%;" onclick="injectScenario()">
  Inject Scenario
</button>
```

### 5c. Scenario Reference (lines 150–168)

Static text panel explaining what each scenario does:
```html
<span style="color:var(--coral); font-weight:700;">Byzantine</span>
Injects corrupted weights from one factory. The server detects and excludes it.

<span style="color:#5B6BDF; font-weight:700;">Re-cluster</span>
Forces adaptive k-means to regroup factories by weight similarity.

<span style="color:var(--green-2); font-weight:700;">Add / Drop</span>
Logs a factory join or disconnect event to the system.
```

---

## 6. JavaScript: WebSocket Listener (lines 177–209)

```javascript
const ws = new WebSocket('{{ ws_url }}');  // 'ws://localhost:8000/ws'

ws.onmessage = function(event) {
  const data = JSON.parse(event.data);

  // ── Event type 1: cluster_assigned ──────────────────────────────
  if (data.type === 'cluster_assigned') {
    addSimLog('cluster', `Factory ${data.factory_id} assigned to Cluster ${data.cluster_id}`);
    const badge = document.getElementById('sim-badge-' + data.factory_id);
    if (badge) {
      badge.textContent = 'Cluster ' + data.cluster_id;
      badge.className   = 'badge-cluster-' + data.cluster_id;
    }
  }

  // ── Event type 2: round_complete ─────────────────────────────────
  if (data.type === 'round_complete') {
    addSimLog('round', `Round ${data.round_num} | Factory ${data.factory_id} | Acc: ${(data.accuracy*100).toFixed(1)}%`);

    // Detect new training session (round 1 when we had rounds > 1 before)
    const lr = document.getElementById('sim-latest-round');
    if (lr && parseInt(lr.textContent) > 1 && data.round_num === 1) {
      // Reset all badges to Unassigned
      document.querySelectorAll('[id^="sim-badge-"]').forEach(b => {
        b.textContent = 'Unassigned';
        b.className   = 'badge-cluster-0';
      });
      document.getElementById('sim-log').innerHTML =
        '<span style="color:#3d454f;">-- new session started --</span><br>';
    }

    if (lr) lr.textContent = data.round_num;
    const tr = document.getElementById('sim-total-rounds');
    if (tr) tr.textContent = data.round_num;
  }

  // ── Event type 3: byzantine_alert ────────────────────────────────
  if (data.type === 'byzantine_alert') {
    addSimLog('alert', `Byzantine alert: Factory ${data.factory_id} flagged - suspicious weights`);
  }
};

ws.onclose = () => setTimeout(() => location.reload(), 5000);
ws.onerror = () => addSimLog('alert', 'WebSocket error - backend may be offline');
```

**WebSocket Payload Shapes:**

| `data.type` | Fields | Action |
|------------|--------|--------|
| `round_complete` | `round_num`, `factory_id`, `accuracy` | Log line + update round counters |
| `cluster_assigned` | `factory_id`, `cluster_id` | Log line + update badge text/class |
| `byzantine_alert` | `factory_id` | Red alert log line |

---

## 7. JavaScript: `addSimLog()` (lines 211–222)

Appends a colored line to the dark terminal div.

```javascript
function addSimLog(type, message) {
  const log = document.getElementById('sim-log');
  if (!log) return;

  const colors = {
    round:   '#4ADE80',   // green   — normal round events
    cluster: '#818CF8',   // indigo  — cluster events
    alert:   '#F87171'    // red     — errors / byzantine
  };

  const now = new Date();
  const t   = now.toTimeString().slice(0, 8);   // "16:25:04"

  const line = document.createElement('div');
  line.style.color = colors[type] || colors.round;
  line.textContent = `[${t}]  ${message}`;

  log.appendChild(line);          // append to bottom
  log.scrollTop = log.scrollHeight; // auto-scroll to latest
}
```

**Color mapping:**
| type | color | Example message |
|------|-------|----------------|
| `'round'` | `#4ADE80` (green) | `[16:25:04]  Round 5 \| Factory 2 \| Acc: 78.3%` |
| `'cluster'` | `#818CF8` (indigo) | `[16:25:10]  Factory 2 assigned to Cluster 1` |
| `'alert'` | `#F87171` (red) | `[16:25:15]  Byzantine alert: Factory 3 flagged` |

---

## 8. JavaScript: Button Click Handlers (lines 224–262)

### Start Button
```javascript
document.getElementById('start-btn')?.addEventListener('click', function() {
  const orig = this.innerHTML;
  this.innerHTML = '<span>Launching terminals...</span>';

  fetch('http://localhost:8000/sim/start', { method: 'POST' })
    .then(() => {
      this.innerHTML = orig;
      addSimLog('round', 'Training launched — check your terminal windows');
    })
    .catch(() => {
      this.innerHTML = orig;
      addSimLog('alert', 'Could not reach /sim/start — is the FL backend running?');
    });
});
```

- `POST http://localhost:8000/sim/start` — FastAPI endpoint that triggers `start_fl.ps1`
- Button text changes to "Launching terminals..." during fetch, resets after
- `?.` optional chaining guards against null if element not found

### Stop Button
```javascript
document.getElementById('stop-btn')?.addEventListener('click', function() {
  fetch('http://localhost:8000/sim/stop', { method: 'POST' })
    .then(() => addSimLog('alert', 'Simulation terminals terminated'))
    .catch(() => addSimLog('alert', 'Could not reach /sim/stop'));
});
```

- `POST http://localhost:8000/sim/stop` — kills the Flower server and client processes

### Scenario Injection
```javascript
function injectScenario() {
  const sel = document.getElementById('scenario-select');
  if (!sel || !sel.value) {
    addSimLog('alert', 'Select a scenario first');
    return;
  }
  const label = sel.options[sel.selectedIndex].text;  // human label for log

  fetch('http://localhost:8000/sim/inject?scenario=' + sel.value, { method: 'POST' })
    .then(() => addSimLog('cluster', `Injected: ${label}`))
    .catch(() => addSimLog('alert', 'Injection failed — backend may be offline'));
}
```

- Reads selected `<option value="">` from dropdown
- `POST http://localhost:8000/sim/inject?scenario=byzantine`
- On success: logs `"Injected: Simulate Byzantine Attack"` in indigo
- On failure: logs red error message

**Valid scenario values:**
| Dropdown option | `sel.value` | Backend action |
|----------------|------------|----------------|
| Simulate Byzantine Attack | `byzantine` | Places `byzantine_flag.txt` in client dir |
| Trigger Re-clustering (k=3) | `recluster` | Forces clustering on next round |
| Add New Factory | `new_factory` | Logs join event |
| Drop Factory Client | `drop_factory` | Logs disconnect event |

---

## 9. Full Page Data Flow Summary

```
Page load:
  views.py → GET /factories, GET /metrics → render simulation.html
  JS → new WebSocket('ws://localhost:8000/ws') → connection established

While training runs (via start_fl.ps1):
  Each factory round → FL server → db_logger.py → FastAPI /ws broadcast
     → ws.onmessage fires:
         round_complete → addSimLog('round', ...) + update sim-latest-round
         cluster_assigned → addSimLog('cluster', ...) + update sim-badge-X
         byzantine_alert → addSimLog('alert', ...)

Start button click:
  fetch POST /sim/start → FastAPI spawns start_fl.ps1 → Flower server + 4 clients start

Stop button click:
  fetch POST /sim/stop → FastAPI kills all FL processes

Scenario injection:
  Select dropdown + click "Inject" → fetch POST /sim/inject?scenario=X → backend acts on it
```
