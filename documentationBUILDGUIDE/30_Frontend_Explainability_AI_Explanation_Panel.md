# 30 — Explainability Page: AI Explanation Panel

**Source file:** `fl_shap_dashboard/templates/pages/explainability.html` (lines 466–512)  
**Data sources:** `context['shap_data']`, `context['top_list']`, `context['selected_scenario']`  
**Layout:** Right column of the same 2-column grid as the SHAP bars (1.4fr : **1fr**)

---

## What It Does
The right panel alongside the SHAP waterfall chart. It contains three distinct sub-sections:
1. **Plain English explanation** — a single paragraph from the SHAP API explaining the prediction
2. **Top 3 Driving Sensors** — ranked list of the 3 most impactful sensors with primary/secondary/tertiary labels
3. **Maintenance Recommendation** — a color-coded action block that changes based on the scenario

---

## Outer Container

```html
<!-- Right column of the grid defined at line 425 -->
<div style="background:var(--card); padding:32px 28px;">

  <span style="color:var(--green-2); font-size:9px; font-weight:700; letter-spacing:0.12em;">
    AI EXPLANATION
  </span>
  <h2 class="font-display" style="font-size:1.6rem; font-weight:700; color:var(--ink); margin:12px 0 20px;">
    Plain English
  </h2>

  <!-- Sub-section 1: explanation text -->
  <!-- Sub-section 2: top sensors list -->
  <!-- Sub-section 3: recommendation box -->

</div>
```

---

## Sub-Section 1: Plain English Explanation (lines 473–476)

```html
<p style="font-size:14px; color:var(--ink); line-height:1.8; margin-bottom:24px;
          border:1.5px solid var(--border); padding:16px;">
  {{ shap_data.explanation }}
</p>
```

`shap_data.explanation` is built by the SHAP API in `shap_api.py`:
```python
explanation = f"{explanation_prefix} Primary driving variables: {', '.join(top3)}."
```

Where `explanation_prefix` is scenario-dependent:
| Scenario | Prefix |
|----------|--------|
| `healthy` | "All monitored sensors operate within optimal baselines. No failure signature detected." |
| `degraded` | "Elevated vibration drift detected. Approaching predictive threshold (40%). Early maintenance scheduling recommended." |
| `random` | "Live inference from NASA CMAPSS test dataset. CNN1D model evaluated real 30-cycle sensor window from the test set." |
| `critical` | "Critical profile identified. High sensor load drives imminent failure probability." |

Then the top 3 sensor IDs are appended: `"... Primary driving variables: sensor_11, sensor_4, sensor_2."`

---

## Sub-Section 2: Top Driving Sensors (lines 478–491)

Label row:
```html
<span style="color:#5B6BDF; font-size:9px; font-weight:700; letter-spacing:0.12em;">
  TOP DRIVING SENSORS
</span>
```

The loop:
```html
<div style="margin-top:10px; display:flex; flex-direction:column; gap:6px;">
  {% for sensor in top_list %}
  <div style="display:flex; align-items:center; gap:8px; padding:7px 10px; background:var(--bg);">

    <!-- Rank number -->
    <span style="font-family:'DM Mono'; font-size:9px; color:var(--muted);">
      {{ sensor.index }}.         <!-- 1, 2, or 3 -->
    </span>

    <!-- Sensor ID + human name -->
    <div>
      <span style="font-family:'DM Mono'; font-size:11px; font-weight:600; color:var(--ink);">
        {{ sensor.id }}           <!-- "sensor_11" -->
      </span>
      <span style="font-family:'Inter'; font-size:10px; color:var(--muted); margin-left:8px;">
        {{ sensor.name }}         <!-- "HPC Outlet Static Pressure" -->
      </span>
    </div>

    <!-- label (primary / secondary / tertiary) pushed to right -->
    <span style="font-family:'DM Mono'; font-size:9px; color:var(--muted); margin-left:auto;">
      {{ sensor.label }} factor   <!-- "primary factor" -->
    </span>

  </div>
  {% endfor %}
</div>
```

### How `top_list` is built in `views.py`

```python
for idx, sensor in enumerate(shap_data['top_sensors']):
    # shap_data['top_sensors'] = ["sensor_11", "sensor_4", "sensor_2"]
    # from SHAP API: top3 = [s[0] for s in sorted_sensors[:3]]

    label = "primary"   if idx == 0 else \
            "secondary" if idx == 1 else "tertiary"

    template_top_list.append({
        'id':     sensor,
        'name':   SENSOR_NAMES.get(sensor, sensor),
        'label':  label,        # "primary", "secondary", "tertiary"
        'index':  idx + 1,      # 1, 2, 3
        'is_pos': shap_data['shap_values'].get(sensor, 0) >= 0
    })
```

**Note:** `top_list` only has 3 items (the top 3 from the SHAP API). `shap_list` has ALL sensors. These are two separate context variables.

---

## Sub-Section 3: Maintenance Recommendation Box (lines 493–509)

This is a left-bordered alert box whose color and text content change based on `selected_scenario`.

```html
<div style="margin-top:20px;
  border-left: 4px solid
    {% if selected_scenario == 'critical' %}var(--coral)
    {% elif selected_scenario == 'degraded' %}var(--gold)
    {% else %}var(--green-2){% endif %};

  padding: 20px 24px;

  background:
    {% if selected_scenario == 'critical' %}var(--coral-bg)
    {% elif selected_scenario == 'degraded' %}var(--gold-bg)
    {% else %}var(--green-bg){% endif %};">

  <!-- Label -->
  <span style="font-family:'DM Mono'; font-size:9px; letter-spacing:0.08em; font-weight:600;
    color:
      {% if selected_scenario == 'critical' %}var(--coral)
      {% elif selected_scenario == 'degraded' %}var(--gold)
      {% else %}var(--green-2){% endif %};">
    MAINTENANCE RECOMMENDATION
  </span>

  <!-- Action text -->
  <p style="font-size:13px; color:var(--ink); line-height:1.7; margin-top:8px;">
    {% if selected_scenario == 'critical' %}
      <strong>Immediate inspection required.</strong>
      Schedule unplanned maintenance within the next 20 engine cycles.
      Focus on: {{ top_list.0.name }}, {{ top_list.1.name }}.

    {% elif selected_scenario == 'degraded' %}
      <strong>Elevated risk — plan maintenance soon.</strong>
      Risk is approaching the 40% failure threshold.
      Schedule a check within 40–60 cycles. Monitor {{ top_list.0.name }} closely.

    {% else %}
      <strong>No immediate action needed.</strong>
      All sensor readings within normal operating range.
      Continue standard monitoring. Next scheduled maintenance at 100+ cycles.
    {% endif %}
  </p>
</div>
```

### Scenario → Visual Mapping

| `selected_scenario` | Border + text color | Background | Message |
|---------------------|--------------------|-----------|---------| 
| `critical` | `var(--coral)` = `#E8521A` | `var(--coral-bg)` = `#FCEAE2` | Immediate inspection, names top 2 sensors |
| `degraded` | `var(--gold)` = `#C99A2E` | `var(--gold-bg)` | Schedule within 40–60 cycles, names sensor_1 |
| `healthy` | `var(--green-2)` = `#146B3A` | `var(--green-bg)` = `#D8EAE0` | No action needed |
| `random` | `var(--green-2)` (falls to `else`) | `var(--green-bg)` | No action needed |

**Note:** `random` falls into the `else` branch — so even if the prediction is FAILURE, the recommendation box says "no action needed". This is because the recommendation box is keyed on `selected_scenario`, not on `shap_data.prediction`. The actual failure state for random is communicated through the Verdict panel (doc 27).

### Template list indexing: `top_list.0.name`
```django
{{ top_list.0.name }}   ← first item's 'name' field (Django dict/list dot notation)
{{ top_list.1.name }}   ← second item's 'name' field
```
Django templates use `.0`, `.1` for list index access (not `[0]` syntax).

---

## Complete Right Panel Visual

```
AI EXPLANATION
Plain English
┌─────────────────────────────────────────────────────────┐
│ Critical profile identified. High sensor load drives    │
│ imminent failure probability. Primary driving           │
│ variables: sensor_11, sensor_4, sensor_2.              │
└─────────────────────────────────────────────────────────┘

TOP DRIVING SENSORS
┌─────────────────────────────────────────────────────────┐
│ 1. sensor_11  HPC Outlet Static Pressure    primary factor │
│ 2. sensor_4   LPT Outlet Temperature      secondary factor │
│ 3. sensor_2   LPC Outlet Temperature       tertiary factor │
└─────────────────────────────────────────────────────────┘

▌MAINTENANCE RECOMMENDATION                    ← coral left border
▌Immediate inspection required. Schedule
▌unplanned maintenance within the next 20
▌engine cycles. Focus on: HPC Outlet Static
▌Pressure, LPT Outlet Temperature.
```
