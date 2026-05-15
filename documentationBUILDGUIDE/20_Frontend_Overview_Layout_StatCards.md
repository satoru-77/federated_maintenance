# 20 — Frontend: Overview Page Layout & Stat Cards (`overview.html` Part 1)

**File:** `fl_shap_dashboard/templates/pages/overview.html`  
**URL:** `/`  
**View:** `views.overview()`  
**Extends:** `base.html`  
**Nav active:** `{% block nav_overview %}active{% endblock %}`

---

## Page Header

```html
<!-- DM Mono tag label (coral) + Space Grotesk h1 + subtitle -->
<span class="tag-label">FEDERATED LEARNING · NASA CMAPSS</span>
<h1 class="font-display" style="font-size:2.4rem;font-weight:800;">
  Training Overview
</h1>
<p style="font-family:'DM Mono',monospace;font-size:11px;color:var(--muted);">
  4 industrial factory clients · CNN1D model · FedAvg aggregation · 20 training rounds
</p>

<!-- Top-right: completed rounds counter -->
<span id="round-num">{{ total_rounds }}</span> / 20
<!-- id="round-num" → updated by WebSocket round_complete events -->
```

---

## 6-Card Stat Row

```html
<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:1px;
  background:var(--border);margin-bottom:32px;">
```

The `gap:1px` on a `var(--border)` background creates hairline separators between cards — a clean line-separated grid without explicit borders.

### Card 1: Global Accuracy

```html
<div style="background:var(--card);padding:22px 18px;">
  <span class="tag-label" style="color:var(--muted);">Global Accuracy</span>
  <div id="m-global-acc" class="stat-num">
    {% if naive_global_acc %}{{ naive_global_acc|pct }}%{% else %}—{% endif %}
  </div>
  <span>{% if n_clusters > 1 %}SINGLE GLOBAL MODEL (BASELINE){% else %}SINGLE GLOBAL MODEL{% endif %}</span>
</div>
```

- **`id="m-global-acc"`** → updated by `round_summary` WebSocket event
- **`naive_global_acc|pct`** → custom Django filter: `(value * 100) | floatformat:1`
- Shows "BASELINE" label once clusters have formed (downgrade context)

### Card 2: Clustered Accuracy

```html
<div style="background:var(--card);padding:22px 18px;">
  <span class="tag-label"
    style="color:{% if n_clusters > 1 %}var(--green-2){% else %}var(--muted){% endif %};">
    Clustered Accuracy
  </span>
  <div id="m-acc" class="stat-num"
    style="color:{% if n_clusters > 1 %}var(--green-2){% else %}var(--muted){% endif %};">
    {% if n_clusters > 1 and clustered_acc %}{{ clustered_acc|pct }}%{% else %}—{% endif %}
  </div>
  <span>
    {% if n_clusters > 1 %}GROUPED · ROUND {{ cluster_round }}+{% else %}AVAILABLE AFTER ROUND 10{% endif %}
  </span>
</div>
```

- **Only shows a value when `n_clusters > 1`** — stays "—" for rounds 1–9
- **`id="m-acc"`** → updated by `round_summary` WebSocket when `clustering_fired: true`
- Label turns green once clustering fires

### Cards 3–6

| Card | Label | Value | ID |
|------|-------|-------|----|
| Factories Online | `var(--coral)` | `{{ factories|length }}` / 4 | none |
| Factory Groups | `#5B6BDF` (indigo) | `{{ n_clusters }}` | `id="m-clusters"` |
| Rounds Done | `var(--gold)` | `{{ total_rounds }}` / 20 | none |
| Latest Round | `var(--muted)` | `{{ metrics.latest_round_num }}` | none |

---

## Cluster Animation Panel

```html
<div style="background:var(--card);border:1.5px solid var(--border);
  margin-bottom:32px;padding:28px 24px;">
  <span class="tag-label-green">Adaptive Clustering</span>
  <h2 class="font-display">Live Cluster Assignments</h2>
  <p>
    {% if cluster_round %}
      K-means clustering triggered at Round {{ cluster_round }} — factories grouped by model weight similarity
    {% else %}
      Cluster assignments reflect the current state stored in the training database
    {% endif %}
  </p>
  <span>ANIMATED · LIVE DATA</span>

  <canvas id="clusterCanvas" width="700" height="220" style="width:100%;display:block;"></canvas>
</div>
```

The `<canvas>` element is 700×220 logical pixels, stretched to 100% container width via CSS. The canvas animation renders inside `{% block extra_scripts %}` — see Doc 21.

---

## Accuracy Chart + Latest Rounds (2-column grid)

```html
<div style="display:grid;grid-template-columns:2fr 1fr;gap:1px;background:var(--border);">

  <!-- Left column (2fr): D3.js chart container -->
  <div style="background:var(--card);padding:28px 24px;">
    <span class="tag-label">Model Performance</span>
    <h2 class="font-display">Accuracy over rounds</h2>
    <div id="d3-chart"></div>   <!-- D3 injects SVG here -->
    <p>↑ Red dashed line = adaptive clustering triggered · Data sourced from training DB</p>
  </div>

  <!-- Right column (1fr): Latest 5 rounds sidebar -->
  <div style="background:var(--card);padding:28px 24px;">
    <span class="tag-label-green">Latest Rounds</span>
    <h2 class="font-display">Round results</h2>
    <div id="latest-rounds-container">
      {% for r in latest_5 %}
        <div style="display:flex;align-items:center;justify-content:space-between;
          padding:10px 0;border-bottom:1px solid var(--border-2);">
          <span>Round {{ r.round_num }}</span>
          <!-- Global accuracy (gray) -->
          <div>
            <span>Global</span>
            <span>{% if r.naive_global %}{{ r.naive_global|pct }}%{% else %}—{% endif %}</span>
          </div>
          <!-- Clustered accuracy (green, only shown after clustering fires) -->
          <div>
            <span>Clustered</span>
            <span>
              {% if r.clustering_fired and r.clustered_accuracy %}{{ r.clustered_accuracy|pct }}%
              {% else %}—{% endif %}
            </span>
          </div>
        </div>
      {% empty %}
        <p>[ NO ROUNDS YET ]</p>
      {% endfor %}
    </div>
  </div>
</div>
```

**`id="latest-rounds-container"`** → WebSocket's `round_summary` handler dynamically inserts new rows (max 5 kept).

---

## Factory Status + Event Log (2-column grid)

```html
<div style="display:grid;grid-template-columns:2fr 1fr;gap:1px;background:var(--border);">

  <!-- Left: Factory status rows -->
  {% for f in factories %}
    <div id="frow-{{ f.factory_id }}">
      <!-- Color dot (green/coral/blue/purple per factory) -->
      <div id="fdot-{{ f.factory_id }}">...</div>
      <!-- Factory name -->
      <span>{{ f.name }}</span>
      <!-- Cluster badge (updates live via WebSocket) -->
      <span id="fcluster-{{ f.factory_id }}" class="badge-cluster-{{ f.cluster_id|default:0 }}">
        {{ f.cluster_label }}
      </span>
      <!-- Live accuracy (populated by WebSocket round_complete, starts as "—") -->
      <span id="facc-{{ f.factory_id }}">—</span>
      <!-- Dataset label (static: FD001/FD002/FD003/FD004) -->
      <span>{{ f.dataset }}</span>
    </div>
  {% endfor %}

  <!-- Right: Event log stream -->
  <div>
    <span class="tag-label">Event Log</span>
    <span>LIVE WHEN TRAINING RUNS</span>
    <h2 class="font-display">WebSocket stream</h2>
    <div id="event-log">
      <!-- Initial placeholder -->
      <div>
        <span>ready</span>
        <span>system</span>
        <span>Waiting for training to start…</span>
      </div>
    </div>
    <p>Events populate automatically when start_all.ps1 is running…</p>
  </div>
</div>
```

### Dynamic Element ID Registry

| ID | Type | Updated by |
|----|------|------------|
| `round-num` | `<span>` | `round_complete` WS — shows current round |
| `m-global-acc` | `<div>` | `round_summary` WS — naive global % |
| `m-acc` | `<div>` | `round_summary` WS — clustered accuracy % |
| `m-clusters` | `<div>` | Not yet wired (static from Django) |
| `facc-{id}` | `<span>` | `round_complete` WS — per-factory accuracy |
| `fcluster-{id}` | `<span>` | `cluster_assigned` WS — badge update |
| `fdot-{id}` | `<div>` | Not updated (static color dot) |
| `latest-rounds-container` | `<div>` | `round_summary` WS — prepends new rows |
| `event-log` | `<div>` | `addEventLog()` — prepends log rows |
| `d3-chart` | `<div>` | `initD3Chart()` on load, updated by `round_summary` |
| `clusterCanvas` | `<canvas>` | `drawFrame()` animation loop |
