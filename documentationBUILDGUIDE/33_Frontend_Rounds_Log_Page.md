# 33 — Rounds Log Page

**Template:** `fl_shap_dashboard/templates/pages/rounds.html`  
**View:** `views.py → def rounds()`  
**URL:** `/rounds/`  
**Purpose:** Complete tabular log of every training round from every factory, with filters and CSV export

---

## 1. Django View Function

```python
@login_required
def rounds(request):
    factory_id = request.GET.get('factory_id')   # optional URL filter
    algorithm  = request.GET.get('algorithm')    # optional URL filter

    # Fetch up to 200 rounds, optionally filtered by factory
    all_rounds  = api_client.get_rounds(factory_id=factory_id, limit=200)
    factories   = api_client.get_factories()
    total_count = len(all_rounds)

    # Algorithm filter applied in Python (not in API call)
    if algorithm:
        all_rounds = [r for r in all_rounds if r['algorithm'] == algorithm]

    # Enrich each round row with display fields
    factory_map = {f['factory_id']: f['name'] for f in factories}
    for r in all_rounds:
        r['factory_name']  = factory_map.get(r['factory_id'], f"Factory {r['factory_id']}")
        r['accuracy_pct']  = round(r['accuracy'] * 100, 1)     # 0.823 → 82.3
        r['cluster_label'] = (f"Cluster {r['cluster_id']}"
                              if r['cluster_id'] is not None else "—")
        r['acc_color'] = (
            'text-green-600' if r['accuracy'] >= 0.85 else
            'text-amber-600' if r['accuracy'] >= 0.70 else
            'text-red-600'
        )

    return render(request, 'pages/rounds.html', {
        'rounds':      all_rounds[:100],   # cap display at 100 rows
        'factories':   factories,
        'total_count': total_count,        # full count before display cap
        'factory_id':  factory_id,
        'algorithm':   algorithm,
        'active_page': 'rounds',
    })
```

**Key details:**
- `get_rounds()` calls `GET /rounds?limit=200&factory_id=X` on FastAPI
- The factory filter is passed to the API; the algorithm filter is applied in Python after
- `all_rounds[:100]` — even if 200 are fetched, only 100 are sent to template
- `total_count` is set before slicing so the header still shows the real total

**`api_client.get_rounds()` function:**
```python
def get_rounds(factory_id=None, limit=100, since=None):
    params = {"limit": limit}
    if factory_id:
        params["factory_id"] = factory_id
    if since:
        params["since"] = since
    return _get("/rounds", params=params) or []
```

**Round dict shape from FastAPI:**
```json
{
  "id": 145,
  "round_num": 7,
  "factory_id": 2,
  "accuracy": 0.823,
  "loss": 0.4312,
  "algorithm": "FedAvg",
  "cluster_id": 1,
  "n_samples": 4200,
  "timestamp": "2026-05-15T16:25:04.123456"
}
```

**Fields added by `views.py`:**
| Field | Example | How computed |
|-------|---------|-------------|
| `factory_name` | `"Factory Berlin"` | Lookup in `factory_map` dict |
| `accuracy_pct` | `82.3` | `round(r['accuracy'] * 100, 1)` |
| `cluster_label` | `"Cluster 1"` or `"—"` | `f"Cluster {r['cluster_id']}"` |
| `acc_color` | `'text-green-600'` | Threshold comparison (not used by template) |

---

## 2. Page Header (lines 7–22)

```html
<h1 class="font-display" style="font-size:2.4rem; font-weight:800;">Training Rounds</h1>
<p style="font-family:'DM Mono'; font-size:11px; color:var(--muted);">
  {{ total_count }} rounds logged · 4 factories
</p>

<!-- Export CSV button (top-right) -->
<button class="btn-outline" onclick="exportCSV()">
  <!-- SVG download icon -->
  Export CSV
</button>
```

`total_count` is the full number fetched from the API (before the 100-row display cap). `{{ rounds|length }}` below the table shows the capped display count.

---

## 3. Filter Bar (lines 24–42)

```html
<div style="display:flex; align-items:center; gap:10px; margin-bottom:20px;">

  <!-- Factory filter dropdown -->
  <select class="fl-select">
    <option>All factories</option>
    <option>Factory Mumbai</option>
    <option>Factory Berlin</option>
    <option>Factory Detroit</option>
    <option>Factory Tokyo</option>
  </select>

  <!-- Algorithm filter dropdown -->
  <select class="fl-select">
    <option>All algorithms</option>
    <option>FedAvg</option>
    <option>FedProx</option>
  </select>

  <!-- Spacer -->
  <div style="flex:1;"></div>

  <!-- Count display -->
  <span style="font-size:10px; color:var(--muted);">
    Showing {{ rounds|length }} of {{ total_count }}
  </span>
</div>
```

> **Important:** These dropdowns are currently **static HTML** — they have no `onchange` handler and no `<form>` wrapping them. The actual filtering happens via URL params (e.g. `/rounds/?factory_id=2`), which are set manually or via links from other pages. The dropdowns are UI placeholders not yet wired to the URL.

The URL-based filtering works because `views.py` reads `request.GET.get('factory_id')` and passes it to the API call.

---

## 4. Rounds Table (lines 44–104)

7-column table. `class="fl-table"` is a CSS class defined in `base.html` for consistent table styling.

```html
<table class="fl-table" style="width:100%; border-collapse:collapse;">
  <thead>
    <tr>
      <th>Round ↕</th>
      <th>Factory</th>
      <th>Accuracy ↕</th>
      <th>Loss</th>
      <th>Algorithm</th>
      <th>Cluster</th>
      <th>Time</th>
    </tr>
  </thead>
  <tbody>
    {% for r in rounds %}
    <tr>
      <!-- Round number -->
      <td>
        <span class="font-display" style="font-weight:700; font-size:15px;">{{ r.round_num }}</span>
      </td>

      <!-- Factory name -->
      <td><span style="font-size:12px;">{{ r.factory_name }}</span></td>

      <!-- Accuracy with color coding -->
      <td>
        <span style="font-weight:700; font-size:14px;
          color: {% if r.accuracy >= 0.85 %}var(--green-2)
                 {% elif r.accuracy >= 0.70 %}#B45309
                 {% else %}var(--coral){% endif %};">
          {{ r.accuracy_pct }}%
        </span>
      </td>

      <!-- Loss (4 decimal places) -->
      <td>
        <span style="font-size:11px; color:var(--muted);">{{ r.loss|floatformat:4 }}</span>
      </td>

      <!-- Algorithm badge -->
      <td>
        <span style="background:var(--green-bg); color:var(--green-2);
                     font-size:9px; padding:2px 8px; letter-spacing:0.06em;">
          {{ r.algorithm }}    <!-- "FedAvg" -->
        </span>
      </td>

      <!-- Cluster badge -->
      <td>
        <span class="badge-cluster-{{ r.cluster_id|default:0 }}">
          {{ r.cluster_label }}   <!-- "Cluster 1" or "—" -->
        </span>
      </td>

      <!-- Timestamp (time only) -->
      <td>
        <span style="font-size:10px; color:var(--muted);">
          {{ r.timestamp|slice:"11:19" }}   <!-- "16:25:04" -->
        </span>
      </td>
    </tr>
    {% empty %}
    <tr>
      <td colspan="7" style="text-align:center; padding:48px;">
        [ NO ROUNDS YET — RUN THE FL SYSTEM FIRST ]
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>
```

**Accuracy color thresholds** (same as factory_detail.html):
| Value | Color |
|-------|-------|
| ≥ 85% | `var(--green-2)` dark green |
| ≥ 70% | `#B45309` amber |
| < 70% | `var(--coral)` orange-red |

**`badge-cluster-{{ r.cluster_id|default:0 }}`:**
- If `r.cluster_id` is `None`, `|default:0` substitutes `0` → `badge-cluster-0` (green badge)
- If cluster assigned, e.g. `cluster_id=1` → `badge-cluster-1` (coral badge)

**Table footer (lines 96–103):**
```html
<div style="padding:12px 14px; border-top:1.5px solid var(--border); background:var(--cream-2);
            display:flex; justify-content:space-between; align-items:center;">
  <span style="font-size:10px; color:var(--muted);">
    showing {{ rounds|length }} / {{ total_count }} rounds
  </span>
  <a href="/rounds/" style="color:var(--green-2);">view all ↗</a>
</div>
```

---

## 5. JavaScript: `exportCSV()` (lines 110–137)

Fetches all rounds from FastAPI and downloads them as a CSV file directly in the browser — no server-side file generation.

```javascript
function exportCSV() {
  // Step 1: Fetch up to 500 rounds from FastAPI directly
  fetch('http://localhost:8000/rounds?limit=500')
    .then(r => r.json())
    .then(data => {

      // Step 2: Define column headers
      const headers = [
        'round_num', 'factory_id', 'accuracy', 'algorithm',
        'cluster_id', 'loss', 'n_samples', 'timestamp'
      ];

      // Step 3: Map each row to CSV values
      const rows = data.map(r =>
        headers.map(h => {
          const val = r[h];
          if (h === 'accuracy') return (val * 100).toFixed(2) + '%';  // 0.82 → "82.00%"
          return val ?? '';   // null/undefined → empty string
        }).join(',')
      );

      // Step 4: Combine header row + data rows
      const csv = [headers.join(','), ...rows].join('\n');

      // Step 5: Create a Blob and trigger browser download
      const blob = new Blob([csv], { type: 'text/csv' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = 'fl_training_rounds.csv';
      document.body.appendChild(a);
      a.click();                         // programmatically click the link
      document.body.removeChild(a);
      URL.revokeObjectURL(url);          // release memory
    })
    .catch(e => alert('Export failed. Make sure FastAPI is running.'));
}
```

**Step-by-step what happens when "Export CSV" is clicked:**
```
1. fetch GET http://localhost:8000/rounds?limit=500  (bypasses Django, goes direct to FastAPI)
2. JSON array of up to 500 round objects returned
3. Build CSV string: header row + one comma-separated row per round
4. Accuracy column converted: 0.823 → "82.30%"
5. null values → empty string (e.g. cluster_id before clustering fires)
6. Blob created in memory → Object URL generated
7. Invisible <a> tag injected into DOM, .click() triggered
8. Browser downloads "fl_training_rounds.csv" instantly
9. <a> tag removed, Object URL revoked (memory freed)
```

**Resulting CSV format:**
```csv
round_num,factory_id,accuracy,algorithm,cluster_id,loss,n_samples,timestamp
1,1,61.20%,FedAvg,,0.7821,4200,2026-05-15T16:10:04.123456
1,2,58.90%,FedAvg,,0.8102,3800,2026-05-15T16:10:05.234567
...
```

---

## 6. Data Flow Summary

```
User visits /rounds/
    ↓
views.py → GET /rounds?limit=200  (FastAPI)
         → GET /factories          (FastAPI)
    ↓
Enriches each round with factory_name, accuracy_pct, cluster_label
Caps display at 100 rows
    ↓
Renders rounds.html:
  - Header: total_count (full number)
  - Filter bar: static dropdowns (visual only)
  - Table: 7 columns, color-coded accuracy, cluster badges
  - Footer: showing X / total

User clicks "Export CSV"
    ↓
exportCSV() → fetch http://localhost:8000/rounds?limit=500
    ↓
Browser downloads fl_training_rounds.csv
```
