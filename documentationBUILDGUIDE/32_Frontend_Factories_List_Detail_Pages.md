# 32 — Factories List & Factory Detail Pages

---

## PART A — Factories List Page (`/factories/`)

**Template:** `fl_shap_dashboard/templates/pages/factories.html`  
**View:** `views.py → def factories()`  
**URL:** `/factories/`

---

### A1. Django View Function

```python
@login_required
def factories(request):
    factories_data = api_client.get_factories()   # GET /factories from FastAPI
    clusters       = api_client.get_clusters()    # GET /clusters from FastAPI

    colors = {1: 'blue', 2: 'purple', 3: 'teal', 4: 'purple'}
    for f in factories_data:
        f['color']         = colors.get(f['factory_id'], 'blue')
        f['cluster_label'] = (f"Cluster {f['cluster_id']}"
                              if f['cluster_id'] is not None
                              else "Unassigned")

    return render(request, 'pages/factories.html', {
        'factories':   factories_data,   # enriched list
        'clusters':    clusters,         # dict of cluster assignments
        'active_page': 'factories',
    })
```

**Enrichment added per factory:**
- `f['color']` — a string label (unused by the template; was used during dev)
- `f['cluster_label']` — `"Cluster 0"` or `"Unassigned"` — used in badge text

**`get_factories()` returns a list of dicts from FastAPI `/factories`:**
```json
[
  {
    "factory_id": 1,
    "name": "Factory Mumbai",
    "dataset": "FD001",
    "n_engines": 100,
    "cluster_id": 0,
    "alpha_value": 0.7,
    "status": "active",
    "cluster_label": "Cluster 0"   ← added by views.py
  },
  ...
]
```

---

### A2. Page Header (lines 7–20)

```html
<h1 class="font-display" style="font-size:2.4rem; font-weight:800;">Factories</h1>
<p style="font-family:'DM Mono'; font-size:11px; color:var(--muted);">
  {{ factories|length }} factories · updates live via WebSocket
</p>

<!-- Live dot indicator (top right) -->
<div style="display:flex; align-items:center; gap:6px; border:1px solid var(--border); padding:6px 14px;">
  <div class="live-dot"></div>
  <span id="factory-status-badge" style="color:var(--green-2);">MONITORING</span>
</div>
```

`id="factory-status-badge"` — not updated by any current JS (reserved for future use).

---

### A3. Factory Cards Grid (lines 22–71)

2-column grid (`grid-template-columns: 1fr 1fr`), one card per factory.

```html
<div style="display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border);">
  {% for f in factories %}
  <a href="/factories/{{ f.factory_id }}/"
     style="display:block; padding:28px 24px; background:var(--card); text-decoration:none;"
     onmouseover="this.style.background='var(--cream-2)'"
     onmouseout="this.style.background='var(--card)'">
```

Each card is a full `<a>` tag — clicking anywhere on the card navigates to `/factories/1/`, `/factories/2/`, etc.

**Hover effect:** Inline `onmouseover`/`onmouseout` — no CSS class needed. Changes background from `var(--card)` to `var(--cream-2)` on hover.

**Arrow indicator (top-right corner):**
```html
<div style="position:absolute; top:0; right:0; width:22px; height:22px;
  background:
    {% if forloop.counter0 == 0 %}var(--green-2)
    {% elif forloop.counter0 == 1 %}var(--coral)
    {% elif forloop.counter0 == 2 %}#5B6BDF
    {% else %}var(--gold){% endif %};
  display:flex; align-items:center; justify-content:center; color:white;">
  &#x2197;   <!-- ↗ northeast arrow unicode -->
</div>
```

Color matches the factory's identity color:
| Loop index | Factory | Arrow color |
|-----------|---------|------------|
| 0 | Mumbai | `var(--green-2)` dark green |
| 1 | Berlin | `var(--coral)` orange |
| 2 | Detroit | `#5B6BDF` indigo |
| 3 | Tokyo | `var(--gold)` amber |

**Live status dot + text:**
```html
<div id="fdot-card-{{ f.factory_id }}"
     style="width:7px; height:7px; border-radius:50%; background:var(--green); animation:live-pulse 2s infinite;">
</div>
<span id="fstatus-card-{{ f.factory_id }}" style="color:var(--green-2);">ACTIVE</span>
```

Updated by WebSocket `round_complete` → `"TRAINING"` and `byzantine_alert` → `"COMPROMISED"`.

**Cluster tag above factory name:**
```html
<span id="fcluster-card-{{ f.factory_id }}" class="tag-label">
  {% if f.cluster_id is not None %}Cluster {{ f.cluster_id }}{% else %}Unassigned{% endif %}
</span>
```

**Stats row — 4 inline stats:**
```html
<div style="display:flex; align-items:center; gap:24px; margin:20px 0;">
  <!-- Dataset -->
  <div>
    <div>{{ f.dataset }}</div>         <!-- "FD001" -->
    <div>DATASET</div>
  </div>
  <!-- Engines -->
  <div>
    <div>{{ f.n_engines }}</div>       <!-- 100 -->
    <div>ENGINES</div>
  </div>
  <!-- Accuracy — starts as "—", updated by WS -->
  <div>
    <div id="facc-card-{{ f.factory_id }}">—</div>
    <div>ACCURACY</div>
  </div>
  <!-- Round — starts as "—", updated by WS -->
  <div>
    <div id="fround-card-{{ f.factory_id }}">—</div>
    <div>ROUND</div>
  </div>
</div>
```

**Cluster badge at bottom of card:**
```html
<span id="fbadge-card-{{ f.factory_id }}" class="badge-cluster-{{ f.cluster_id|default:0 }}">
  {{ f.cluster_label }}   <!-- "Cluster 0" or "Unassigned" -->
</span>
```

`badge-cluster-0/1/2/3` CSS classes are defined in `base.html`:
```css
.badge-cluster-0 { color:var(--green);  background:var(--green-bg); border-color:var(--green-lt); }
.badge-cluster-1 { color:var(--coral);  background:var(--coral-bg); border-color:var(--coral-lt); }
.badge-cluster-2 { color:#1D4ED8;       background:#EFF6FF;         border-color:#93C5FD; }
.badge-cluster-3 { color:#7C3AED;       background:#F5F3FF;         border-color:#C4B5FD; }
```

---

### A4. WebSocket Listener (lines 87–133)

Handles 3 event types, updating card elements live:

```javascript
function connectWS() {
  ws = new WebSocket('{{ ws_url }}');

  ws.onmessage = function(event) {
    const data = JSON.parse(event.data);

    // ── round_complete: update accuracy + round number ──────────
    if (data.type === 'round_complete') {
      const fid = data.factory_id;
      document.getElementById('facc-card-'    + fid).textContent = (data.accuracy * 100).toFixed(1) + '%';
      document.getElementById('fround-card-'  + fid).textContent = 'R' + data.round_num;
      document.getElementById('fdot-card-'    + fid).style.background = 'var(--green)';
      document.getElementById('fstatus-card-' + fid).textContent = 'TRAINING';
    }

    // ── cluster_assigned: update cluster label + badge ──────────
    if (data.type === 'cluster_assigned') {
      const fid = data.factory_id;
      const cid = data.cluster_id;
      document.getElementById('fcluster-card-' + fid).textContent = 'Cluster ' + cid;
      const badge = document.getElementById('fbadge-card-' + fid);
      badge.textContent = 'Cluster ' + cid;
      badge.className   = 'badge-cluster-' + cid;  // changes color scheme
    }

    // ── byzantine_alert: turn dot red + COMPROMISED status ──────
    if (data.type === 'byzantine_alert') {
      const fid = data.factory_id;
      document.getElementById('fdot-card-'    + fid).style.background = '#EF4444';
      const sts = document.getElementById('fstatus-card-' + fid);
      sts.textContent  = 'COMPROMISED';
      sts.style.color  = '#EF4444';
    }
  };

  ws.onclose = () => setTimeout(connectWS, 5000);  // auto-reconnect after 5s
}
connectWS();
```

**DOM element IDs per factory (e.g. factory_id=2):**
| ID | Initial value | Updated by |
|----|--------------|-----------|
| `fdot-card-2` | green pulsing | `round_complete` → green, `byzantine_alert` → `#EF4444` |
| `fstatus-card-2` | `"ACTIVE"` | `round_complete` → `"TRAINING"`, `byzantine_alert` → `"COMPROMISED"` |
| `facc-card-2` | `"—"` | `round_complete` → `"82.3%"` |
| `fround-card-2` | `"—"` | `round_complete` → `"R7"` |
| `fcluster-card-2` | `"Unassigned"` | `cluster_assigned` → `"Cluster 1"` |
| `fbadge-card-2` | `badge-cluster-0` | `cluster_assigned` → `badge-cluster-1` + new text |

---

---

## PART B — Factory Detail Page (`/factories/<id>/`)

**Template:** `fl_shap_dashboard/templates/pages/factory_detail.html`  
**View:** `views.py → def factory_detail(factory_id)`  
**URL:** `/factories/1/`, `/factories/2/`, etc.  
**Template tag:** `{% load custom_filters %}` — uses `pct` and `floatformat` custom filters

---

### B1. Django View Function

```python
@login_required
def factory_detail(request, factory_id):
    factory = api_client.get_factory(factory_id)   # GET /factories/{factory_id}
    if not factory:
        raise Http404("Factory not found")

    rounds = factory.get('recent_rounds', [])
    for r in rounds:
        r['accuracy_pct'] = round(r['accuracy'] * 100, 1)  # 0.823 → 82.3

    return render(request, 'pages/factory_detail.html', {
        'factory':    factory,
        'rounds':     rounds,
        'chart_data': [{'round': r['round_num'], 'accuracy': r['accuracy']}
                       for r in reversed(rounds)],  # ascending order for chart
        'active_page': 'factories',
    })
```

`api_client.get_factory(factory_id)` calls `GET /factories/{factory_id}` which returns a single factory dict including `recent_rounds` list from the last N rounds in the DB.

---

### B2. Breadcrumb (lines 8–13)

```html
<div style="font-family:'DM Mono'; font-size:10px; letter-spacing:0.08em;">
  <a href="/factories/" style="color:var(--muted);">FACTORIES</a>
  <span>→</span>
  <span style="color:var(--ink);">{{ factory.name|upper }}</span>
</div>
```

---

### B3. Stat Grid — 4 Cards (lines 29–47)

```html
<div style="display:grid; grid-template-columns:repeat(4,1fr); gap:0; border:1.5px solid var(--border);">

  <!-- Dataset -->
  <div style="padding:24px 20px;">
    <span class="tag-label">Dataset</span>
    <div class="stat-num">{{ factory.dataset }}</div>    <!-- "FD001" -->
  </div>

  <!-- Best Alpha (α) — from personalization -->
  <div style="padding:24px 20px; border-left:1.5px solid var(--border);">
    <span class="tag-label">Best Alpha (α)</span>
    <div class="stat-num">{{ factory.alpha_value|default:"—" }}</div>  <!-- e.g. "0.7" -->
  </div>

  <!-- Cluster ID -->
  <div style="padding:24px 20px; border-left:1.5px solid var(--border);">
    <span class="tag-label">Cluster ID</span>
    <div class="stat-num">{{ factory.cluster_id|default:"—" }}</div>   <!-- e.g. "0" -->
  </div>

  <!-- Total rounds -->
  <div style="padding:24px 20px; border-left:1.5px solid var(--border);">
    <span class="tag-label">Rounds</span>
    <div class="stat-num">{{ rounds|length }}</div>    <!-- count of recent_rounds -->
  </div>

</div>
```

`alpha_value` is set by the Personalization system (grid search). It represents the optimal blending coefficient: `final_weights = α * cluster_weights + (1-α) * local_weights`.

---

### B4. Accuracy Chart (lines 49–59, script lines 101–136)

A `<canvas>` element rendered by **Chart.js** (loaded from CDN):

```html
<canvas id="factoryChart" height="80"></canvas>
```

```javascript
const chartData = {{ chart_data|safe }};
// e.g. [{"round": 1, "accuracy": 0.612}, {"round": 2, "accuracy": 0.734}, ...]

const ctx = document.getElementById('factoryChart').getContext('2d');
new Chart(ctx, {
  type: 'line',
  data: {
    labels:   chartData.map(d => 'R' + d.round),      // ["R1", "R2", ...]
    datasets: [{
      label:           'Accuracy',
      data:            chartData.map(d => d.accuracy), // [0.612, 0.734, ...]
      borderColor:     '#1A3D2B',                       // dark green line
      backgroundColor: 'rgba(26,61,43,0.06)',           // faint green fill
      borderWidth:     2,
      pointRadius:     3,
      fill:            true,
      tension:         0.35                             // smooth bezier curve
    }]
  },
  options: {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      y: {
        min: 0, max: 1,
        ticks: { callback: v => (v*100).toFixed(0) + '%' }  // 0.82 → "82%"
      }
    }
  }
});
```

**Note:** Uses `Chart.js` (not D3.js like the Overview page). Simpler API, loaded from CDN `cdn.jsdelivr.net/npm/chart.js`.

---

### B5. Recent Rounds Table (lines 61–96)

```html
<table class="fl-table" style="width:100%; border-collapse:collapse;">
  <thead>
    <tr>
      <th>Round</th> <th>Accuracy</th> <th>Loss</th> <th>Algorithm</th> <th>Time</th>
    </tr>
  </thead>
  <tbody>
    {% for r in rounds %}
    <tr>
      <!-- Round number -->
      <td><span class="font-display" style="font-weight:700; font-size:15px;">{{ r.round_num }}</span></td>

      <!-- Accuracy with color coding -->
      <td>
        <span style="font-weight:700; font-size:14px;
          color: {% if r.accuracy >= 0.85 %}var(--green-2)
                 {% elif r.accuracy >= 0.70 %}#B45309
                 {% else %}var(--coral){% endif %};">
          {{ r.accuracy_pct }}%
        </span>
      </td>

      <!-- Loss value -->
      <td><span style="font-size:11px; color:var(--muted);">{{ r.loss|floatformat:4 }}</span></td>

      <!-- Algorithm badge -->
      <td>
        <span style="background:var(--green-bg); color:var(--green-2); font-size:9px; padding:2px 8px;">
          {{ r.algorithm }}    <!-- "FedAvg" or "Clustered" -->
        </span>
      </td>

      <!-- Timestamp — sliced to show only HH:MM:SS -->
      <td><span style="font-size:10px; color:var(--muted);">{{ r.timestamp|slice:"11:19" }}</span></td>
    </tr>
    {% empty %}
    <tr><td colspan="5" style="text-align:center;">[ NO ROUNDS YET ]</td></tr>
    {% endfor %}
  </tbody>
</table>
```

**Accuracy color thresholds:**
| Value | Color | CSS variable |
|-------|-------|-------------|
| ≥ 85% | Green | `var(--green-2)` = `#146B3A` |
| ≥ 70% | Amber | `#B45309` |
| < 70% | Coral | `var(--coral)` = `#E8521A` |

**Timestamp slicing:**
```django
{{ r.timestamp|slice:"11:19" }}
```
`r.timestamp` is a full ISO string like `"2026-05-15T16:25:04.123456"`. `slice:"11:19"` extracts characters 11–18 = `"16:25:04"`.

---

## Navigation Flow

```
/factories/          ← factories list (2×2 card grid)
     ↓ click card
/factories/1/        ← factory_detail for Mumbai (stat grid + chart + rounds table)
/factories/2/        ← factory_detail for Berlin
/factories/3/        ← factory_detail for Detroit
/factories/4/        ← factory_detail for Tokyo
```
