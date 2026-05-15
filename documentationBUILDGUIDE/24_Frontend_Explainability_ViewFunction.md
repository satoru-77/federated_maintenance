# Doc F1 — Explainability Page: Comprehensive Build Guide
**File:** `fl_shap_dashboard/templates/pages/explainability.html`  
**View:** `fl_shap_dashboard/dashboard/views.py → def explainability()`  
**URL:** `/explainability/?factory_id=1&scenario=critical`

---

## PART 1 — Django View Function (`def explainability()`)

### Location
`fl_shap_dashboard/dashboard/views.py`, line 172

### Entry Point
This view is called when a user navigates to `/explainability/`. It is decorated with `@login_required` — unauthenticated users are redirected to `/login/`.

### Step-by-Step Execution

**Step 1 — Read URL parameters**
```python
factory_id = int(request.GET.get('factory_id', 1))   # default: Factory 1 (Mumbai)
scenario   = request.GET.get('scenario', 'critical')  # default: 'critical'
```
Both come from the URL query string. Example: `/explainability/?factory_id=2&scenario=random`

Valid values for `scenario`: `'critical'`, `'healthy'`, `'degraded'`, `'random'`

---

**Step 2 — Decide whether to use cache or fetch fresh data**
```python
cache_key   = f"{factory_id}:{scenario}"   # e.g. "1:critical"
force_fresh = bool(request.GET.get('t'))   # 't' param present = bypass cache
```
The module-level `_SHAP_CACHE = {}` dict persists for the lifetime of the Django process.

Cache logic (pseudocode):
```
IF scenario is NOT 'random'
   AND no 't' param in URL
   AND cache_key already in _SHAP_CACHE:
     use cached result → skip the HTTP call to SHAP API
ELSE:
     fetch fresh from SHAP API
     IF scenario is NOT 'random': store in cache for next time
```

> **Why?** The `critical`, `healthy`, and `degraded` scenarios use deterministic random seeds in `shap_api.py`, so they always produce the same result. No need to call the API again. The `random` scenario picks a different live engine each time, so it is NEVER cached.

---

**Step 3 — Call the SHAP API**
```python
response = requests.post(
    "http://localhost:8001/explain/demo",
    params={"factory_id": factory_id, "scenario": scenario},
    timeout=10
)
```
- Method: `POST`
- Port: `8001` (standalone SHAP API service)
- Endpoint: `/explain/demo`
- If the SHAP API is offline (connection refused), the `except` block silently sets `shap_data = None` and the template renders an "API Offline" fallback state.

**Confidence multiplied by 100:**
```python
if 'confidence' in shap_data:
    shap_data['confidence'] = round(shap_data['confidence'] * 100, 1)
```
The SHAP API returns `confidence` as a float `0.0–1.0`. Django multiplies by 100 so the template can display `85.4%` directly.

---

**Step 4 — SENSOR_NAMES lookup dictionary**
```python
SENSOR_NAMES = {
    'sensor_1':  'Fan Inlet Temperature',
    'sensor_2':  'LPC Outlet Temperature',
    'sensor_3':  'HPC Outlet Temperature',
    ...
    'sensor_21': 'Low-Pres Turbine Cool Flow',
}
```
21 entries total (all NASA CMAPSS sensors). Used to convert machine keys like `sensor_11` into human-readable names like `HPC Outlet Static Pressure` for display in the SHAP bar chart.

---

**Step 5 — Build `template_shap_list` (the SHAP waterfall bars)**
```python
max_abs = max([abs(v) for v in shap_data['shap_values'].values()])

for sensor, value in shap_data['shap_values'].items():
    pct = min((abs(value) / max_abs) * 50, 50)   # max bar = 50% of available width
    template_shap_list.append({
        'id':     sensor,          # e.g. 'sensor_11'
        'name':   SENSOR_NAMES.get(sensor, sensor),
        'value':  value,           # raw SHAP value (negative or positive float)
        'is_pos': value >= 0,      # True = coral bar (failure direction)
        'pct':    pct              # CSS width percentage (0–50)
    })
```
The `shap_values` dict from the API is already sorted by `abs(value)` descending (most important sensor first).

---

**Step 6 — Build `template_top_list` (Top 3 driving sensors panel)**
```python
for idx, sensor in enumerate(shap_data['top_sensors']):
    label = "primary" if idx == 0 else ("secondary" if idx == 1 else "tertiary")
    # ... sparkline generation (deterministic based on scenario)
    template_top_list.append({
        'id':       sensor,
        'name':     SENSOR_NAMES.get(sensor, sensor),
        'label':    label,
        'index':    idx + 1,
        'is_pos':   shap_data['shap_values'].get(sensor, 0) >= 0
    })
```

---

**Step 7 — Build `raw_sensor_rows` (for Random scenario only)**
```python
if shap_data and shap_data.get('raw_sensor_sample'):
    for sensor, val in shap_data['raw_sensor_sample'].items():
        raw_sensor_rows.append({
            'id':    sensor,
            'name':  SENSOR_NAMES.get(sensor, sensor),
            'value': val,
        })
```
Only populated when `scenario='random'`. The `raw_sensor_sample` field from the SHAP API contains the unscaled (real engineering unit) sensor readings from cycle 1 of the selected window.

---

**Step 8 — Render template with context**
```python
return render(request, 'pages/explainability.html', {
    'factories':           factories,           # list of all 4 factories (for selector bar)
    'selected_factory_id': factory_id,          # which factory tab is active
    'selected_scenario':   scenario,            # which scenario card is active
    'shap_data':           shap_data,           # full SHAP API response (or None)
    'shap_list':           template_shap_list,  # processed list for SHAP bar chart
    'top_list':            template_top_list,   # top 3 sensors list
    'raw_sensor_rows':     raw_sensor_rows,     # raw sensor values (random only)
    'validation_data':     validation_data,     # optional JSON proof file
    'active_page':         'explain',           # highlights 'Explain' in nav
})
```

---

## STATUS
- [x] Part 1: Django view function (`def explainability()`)
- [ ] Part 2: Page header + Factory selector bar (HTML + Django template loop)
- [ ] Part 3: Engine Fleet selector — 4 cards, JS loadCard(), shuffleEngine()
- [ ] Part 4: Prediction Result panel — Verdict, Confidence score, RUL
- [ ] Part 5: Live Dataset Verification block (random scenario only)
- [ ] Part 6: SHAP waterfall bar chart — HTML rendering + how bars are sized
- [ ] Part 7: AI Explanation panel — top sensors list, maintenance recommendation
- [ ] Part 8: Offline fallback state
