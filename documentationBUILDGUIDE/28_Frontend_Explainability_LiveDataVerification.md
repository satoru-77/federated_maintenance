# 28 — Explainability Page: Live Dataset Verification Block

**Source file:** `fl_shap_dashboard/templates/pages/explainability.html` (lines 305–421)  
**Condition:** `{% if selected_scenario == 'random' and shap_data.engine_id %}`  
**Context variables:** `shap_data`, `raw_sensor_rows`

---

## What It Does
This entire block only renders when the user is in **random mode** and a real engine was successfully fetched. It is an academic-integrity panel that proves the CNN made a real inference — not a hardcoded demo.

It shows:
1. A side-by-side **CNN Prediction vs Actual Dataset Label** panel
2. A 5-column **traceability info bar** (dataset file, engine ID, cycle range, total cycles, sensor count)
3. The **exact sensor column names** fed into the model
4. A **raw sensor value grid** showing the unscaled readings from cycle 1 of the selected window

---

## Render Condition

```django
{% if selected_scenario == 'random' and shap_data.engine_id %}
```

Both conditions must be true:
- `selected_scenario == 'random'` — URL param `scenario=random`
- `shap_data.engine_id` — the SHAP API successfully returned an engine ID (not None)

For `critical`, `healthy`, `degraded` scenarios, `shap_data.engine_id` is always `None` because those use synthetic sensor windows, so this entire block is hidden.

---

## Section 1: Indigo Header Bar (lines 309–326)

```html
<div style="margin-bottom:32px; border:2px solid #5B6BDF; background:var(--card);">

  <!-- Header bar with indigo background -->
  <div style="background:#5B6BDF; padding:14px 24px;
              display:flex; align-items:center; justify-content:space-between;">
    <div>
      <span style="color:rgba(255,255,255,0.7); font-size:9px; font-weight:600;">
        LIVE DATASET VERIFICATION
      </span>
      <div style="color:white; font-size:14px; font-weight:700; margin-top:2px;">
        Engine #{{ shap_data.engine_id }} — Real Data Fetched from {{ shap_data.dataset_file }}
      </div>
    </div>

    <!-- Match/mismatch badge in top-right -->
    {% if shap_data.prediction == shap_data.actual_label %}
      <span style="background:var(--green-2); color:white; font-size:10px; font-weight:700; padding:6px 14px;">
        PREDICTION CORRECT
      </span>
    {% else %}
      <span style="background:var(--coral); color:white; ...">PREDICTION MISMATCH</span>
    {% endif %}
  </div>
```

The heading dynamically shows: `Engine #47 — Real Data Fetched from test_FD001.txt`

---

## Section 2: Side-by-Side Comparison (lines 328–365)

Two equal columns: left = CNN output, right = ground truth from dataset.

```html
<div style="display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border);">

  <!-- LEFT: CNN Model Predicted -->
  <div style="background:var(--card); padding:28px 24px;">
    <span style="color:#5B6BDF; font-size:9px; font-weight:700;">CNN MODEL PREDICTED</span>

    <!-- Big FAILURE / HEALTHY word -->
    <span style="font-size:3rem; font-weight:800;
      color: {% if shap_data.prediction == 'FAILURE' %}var(--coral){% else %}var(--green-2){% endif %};">
      {% if shap_data.prediction == 'FAILURE' %}FAILURE{% else %}HEALTHY{% endif %}
    </span>

    <div>Confidence: <strong>{{ shap_data.confidence|floatformat:1 }}%</strong></div>

    <p>The CNN1D model received 30 cycles (cycles {{ shap_data.start_cycle }}–{{ shap_data.end_cycle }})
       of sensor readings from Engine #{{ shap_data.engine_id }} and produced this classification.</p>
  </div>

  <!-- RIGHT: Actual Ground Truth -->
  <!-- Background changes based on match/mismatch -->
  <div style="background:
    {% if shap_data.prediction == shap_data.actual_label %}var(--green-bg){% else %}var(--coral-bg){% endif %};
    padding:28px 24px;">
    
    <span style="color:var(--muted); font-size:9px; font-weight:700;">ACTUAL LABEL IN DATASET</span>

    <span style="font-size:3rem; font-weight:800;
      color: {% if shap_data.actual_label == 'FAILURE' %}var(--coral){% else %}var(--green-2){% endif %};">
      {% if shap_data.actual_label == 'FAILURE' %}FAILURE{% else %}HEALTHY{% endif %}
    </span>

    <div>Actual RUL: <strong>{{ shap_data.actual_rul }} cycles</strong> remaining</div>

    <p>Fetched from <strong>{{ shap_data.rul_file }}</strong>.
       An engine is labelled FAILURE when RUL ≤ 30 cycles.
       This engine has {{ shap_data.actual_rul }} cycles left → labelled as {{ shap_data.actual_label }}.</p>
  </div>
</div>
```

**Right panel background color logic:**
```django
background: {% if shap_data.prediction == shap_data.actual_label %}
    var(--green-bg)   ← light green when correct
{% else %}
    var(--coral-bg)   ← light coral/red when mismatch
{% endif %}
```

**Context variables used here:**

| Variable | Source | Example |
|----------|--------|---------|
| `shap_data.engine_id` | SHAP API `/explain/demo` random | `47` |
| `shap_data.prediction` | SHAP API | `"FAILURE"` |
| `shap_data.actual_label` | SHAP API (from RUL file) | `"FAILURE"` |
| `shap_data.confidence` | SHAP API × 100 by views.py | `81.2` |
| `shap_data.actual_rul` | SHAP API (from RUL file) | `18` |
| `shap_data.start_cycle` | SHAP API (window start) | `82` |
| `shap_data.end_cycle` | SHAP API (window end) | `111` |
| `shap_data.rul_file` | SHAP API | `"RUL_FD001.txt"` |
| `shap_data.dataset_file` | SHAP API | `"test_FD001.txt"` |

---

## Section 3: Traceability Info Bar (lines 367–389)

A 5-column grid showing metadata proving exactly where the data came from.

```html
<div style="background:var(--bg); padding:16px 24px; border-top:1.5px solid var(--border);
            display:grid; grid-template-columns:repeat(5,1fr); gap:16px;">
  
  <!-- Column 1: Test Dataset -->
  <div>
    <div style="font-size:8px; color:var(--muted); letter-spacing:0.06em;">TEST DATASET</div>
    <div style="font-size:11px; font-weight:600;">{{ shap_data.dataset_file }}</div>
  </div>

  <!-- Column 2: Engine ID -->
  <div>
    <div style="font-size:8px; color:var(--muted);">ENGINE ID</div>
    <div style="font-size:11px; font-weight:600; color:#5B6BDF;">#{{ shap_data.engine_id }}</div>
  </div>

  <!-- Column 3: Cycle range used -->
  <div>
    <div style="font-size:8px; color:var(--muted);">CYCLES USED</div>
    <div style="font-size:11px; font-weight:600;">{{ shap_data.start_cycle }} → {{ shap_data.end_cycle }}</div>
  </div>

  <!-- Column 4: Total engine life -->
  <div>
    <div style="font-size:8px; color:var(--muted);">TOTAL ENGINE CYCLES</div>
    <div style="font-size:11px; font-weight:600;">{{ shap_data.total_engine_cycles }}</div>
  </div>

  <!-- Column 5: Sensor count -->
  <div>
    <div style="font-size:8px; color:var(--muted);">SENSORS USED</div>
    <div style="font-size:11px; font-weight:600;">{{ shap_data.sensor_columns|length }} columns</div>
  </div>
</div>
```

`shap_data.sensor_columns` is a list (e.g. `["sensor_2", "sensor_3", ..., "sensor_21"]`). The `|length` filter counts the list without rendering it.

---

## Section 4: Sensor Columns Used (lines 391–399)

Shows each sensor name used as a small pill badge.

```html
<div style="background:var(--bg); padding:12px 24px; border-top:1px solid var(--border-2);">
  <div style="font-size:8px; color:var(--muted); letter-spacing:0.06em; margin-bottom:8px;">
    SENSOR COLUMNS FED INTO MODEL
  </div>
  <div style="display:flex; flex-wrap:wrap; gap:6px;">
    {% for col in shap_data.sensor_columns %}
    <span style="font-family:'DM Mono'; font-size:9px; padding:3px 8px;
                 background:var(--card); border:1px solid var(--border); color:var(--ink);">
      {{ col }}
    </span>
    {% endfor %}
  </div>
</div>
```

`shap_data.sensor_columns` comes directly from the SHAP API response. For Factory 1 it is:
```
["sensor_2","sensor_3","sensor_4","sensor_7","sensor_8","sensor_9",
 "sensor_11","sensor_12","sensor_13","sensor_14","sensor_15","sensor_17","sensor_20","sensor_21"]
```
14 pills rendered for Factory 1, 19 for Factory 2/4, 16 for Factory 3.

---

## Section 5: Raw Sensor Values Grid (lines 401–419)

Shows the unscaled engineering values from the first row of the 30-cycle window.

```html
{% if raw_sensor_rows %}
<div style="background:var(--bg); padding:12px 24px; border-top:1px solid var(--border-2);">
  <div style="font-size:8px; color:var(--muted); margin-bottom:10px;">
    RAW SENSOR VALUES — Cycle {{ shap_data.start_cycle }} (first row of window, before scaling)
  </div>
  <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:8px;">
    {% for row in raw_sensor_rows %}
    <div style="display:flex; justify-content:space-between; padding:6px 10px;
                background:var(--card); border:1px solid var(--border-2);">
      <div>
        <span style="font-size:11px; font-weight:600;">{{ row.id }}</span><br>
        <span style="font-size:10px; color:var(--muted);">{{ row.name }}</span>
      </div>
      <span style="font-size:13px; color:#5B6BDF; font-weight:600; align-self:center;">
        {{ row.value }}
      </span>
    </div>
    {% endfor %}
  </div>
</div>
{% endif %}
```

**How `raw_sensor_rows` is built in `views.py`:**
```python
raw_sensor_rows = []
if shap_data and shap_data.get('raw_sensor_sample'):
    for sensor, val in shap_data['raw_sensor_sample'].items():
        raw_sensor_rows.append({
            'id':    sensor,                          # e.g. "sensor_2"
            'name':  SENSOR_NAMES.get(sensor, sensor), # e.g. "LPC Outlet Temperature"
            'value': val,                             # e.g. 642.35  (real engineering unit)
        })
```

**Where `raw_sensor_sample` comes from in shap_api.py:**
```python
# In /explain/demo → scenario=random:
edf_raw = df_raw[df_raw['engine_id'] == random_engine].sort_values('cycle')
raw_row = edf_raw.iloc[start_idx][sensor_cols].to_dict()
raw_sensor_sample = {k: round(float(v), 4) for k, v in raw_row.items()}
```
`df_raw` is the CSV loaded WITHOUT scaling applied — so values are in real engineering units (temperatures in Rankine, pressures in psia, speeds in rpm).

---

## Visual Summary

```
╔══════════════════════════════════════════════════════════════════╗
║  LIVE DATASET VERIFICATION                    [PREDICTION CORRECT]
║  Engine #47 — Real Data Fetched from test_FD001.txt              ║
╠══════════════════════════════════════════════════════════════════╣
║  CNN MODEL PREDICTED    │        ACTUAL LABEL IN DATASET         ║
║  FAILURE (coral)        │  FAILURE (coral)  ← green-bg or coral  ║
║  Confidence: 81.2%      │  Actual RUL: 18 cycles                 ║
║  cycles 82–111          │  Fetched from RUL_FD001.txt            ║
╠══════════════════════════════════════════════════════════════════╣
║  TEST DATASET │ ENGINE ID │ CYCLES USED │ TOTAL CYCLES │ SENSORS ║
║  test_FD001   │   #47     │  82 → 111  │     130      │  14     ║
╠══════════════════════════════════════════════════════════════════╣
║  SENSOR COLUMNS: [sensor_2] [sensor_3] [sensor_4] ... (14 pills) ║
╠══════════════════════════════════════════════════════════════════╣
║  RAW VALUES: sensor_2: 642.35 │ sensor_3: 1589.3 │ sensor_4: ... ║
╚══════════════════════════════════════════════════════════════════╝
```
