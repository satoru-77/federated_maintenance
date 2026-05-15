# 29 — Explainability Page: SHAP Waterfall Bar Chart

**Source file:** `fl_shap_dashboard/templates/pages/explainability.html` (lines 424–464)  
**Data source:** `context['shap_list']` built in `views.py → def explainability()`  
**Layout:** Left column of a 2-column grid (1.4fr : 1fr)

---

## What It Does
Renders one horizontal bar per sensor. Bars extend either:
- **Right (coral/orange)** — sensor pushes prediction toward **FAILURE**
- **Left (green)** — sensor pushes prediction toward **HEALTHY**

A vertical center line divides the chart. All bars are normalized so the strongest sensor always fills 50% of available width (the maximum), and others are proportionally smaller.

---

## Data Flow: SHAP API → Template

### Step 1 — SHAP API returns `shap_values` dict
From `POST /explain/demo`, inside `SHAPResponse`:
```json
{
  "shap_values": {
    "sensor_11": 0.03241,
    "sensor_4":  0.02891,
    "sensor_2":  -0.01543,
    "sensor_7":  -0.00921,
    ...
  },
  "top_sensors": ["sensor_11", "sensor_4", "sensor_2"]
}
```
Already sorted by `abs(value)` descending — most impactful sensor first.

### Step 2 — `views.py` builds `template_shap_list`
```python
max_abs = max([abs(v) for v in shap_data['shap_values'].values()])
# max_abs = 0.03241 (the strongest sensor's magnitude)

for sensor, value in shap_data['shap_values'].items():
    pct = min((abs(value) / max_abs) * 50, 50)
    # Formula: normalize to [0, 50] range
    # sensor_11: (0.03241 / 0.03241) * 50 = 50.0  ← fills half the bar area
    # sensor_4:  (0.02891 / 0.03241) * 50 = 44.6
    # sensor_2:  (0.01543 / 0.03241) * 50 = 23.8

    template_shap_list.append({
        'id':     sensor,                           # "sensor_11"
        'name':   SENSOR_NAMES.get(sensor, sensor), # "HPC Outlet Static Pressure"
        'value':  value,                            # 0.03241 (raw float, signed)
        'is_pos': value >= 0,                       # True → coral bar (failure direction)
        'pct':    pct                               # 50.0 → CSS width percentage
    })
```

**Why multiply by 50 and cap at 50?**  
The bar chart has a center line at 50% of the container width. Positive bars grow right from center (left:50%), negative bars grow left from center (right:50%). So max bar width = 50% of container = fills exactly half the available space.

### Step 3 — Template renders list
Each item in `shap_list` becomes one row in the chart.

---

## Outer Container (lines 425–435)

```html
<!-- 2-column grid: SHAP bars (left) | AI explanation (right) -->
<div style="display:grid; grid-template-columns:1.4fr 1fr; gap:1px;
            background:var(--border); margin-bottom:32px;
            box-shadow:0 2px 12px rgba(0,0,0,0.06);">

  <!-- Left column: SHAP bars -->
  <div style="background:var(--card); padding:32px 28px;">
    <span style="color:var(--coral); font-size:9px; font-weight:700; letter-spacing:0.12em;">
      SHAP FEATURE ATTRIBUTION
    </span>
    <h2 class="font-display" style="font-size:1.6rem; font-weight:700; color:var(--ink); margin:12px 0 6px;">
      Why did the model predict this?
    </h2>
    <p style="font-size:10px; color:var(--muted); margin-bottom:24px;">
      Coral = pushes toward FAILURE &nbsp;·&nbsp; Green = pushes toward HEALTHY
    </p>

    <!-- Bar rows container -->
    <div style="display:flex; flex-direction:column; gap:12px;">
      {% for sensor in shap_list %}
        <!-- one row per sensor -->
      {% endfor %}
    </div>
  </div>
```

---

## Single Bar Row HTML (lines 439–461)

This is the template for each sensor row. The `{% for sensor in shap_list %}` loop renders this once per sensor.

```html
<div style="display:flex; align-items:center; gap:10px;">

  <!-- Sensor label: code name + human-readable name -->
  <div style="min-width:160px; line-height:1.3;">
    <span style="font-family:'DM Mono'; font-size:11px; font-weight:600; color:var(--ink);">
      {{ sensor.id }}          <!-- e.g. "sensor_11" -->
    </span><br>
    <span style="font-family:'Inter'; font-size:10px; color:var(--muted);">
      {{ sensor.name }}        <!-- e.g. "HPC Outlet Static Pressure" -->
    </span>
  </div>

  <!-- Bar track: full-width gray background with center line -->
  <div style="flex:1; position:relative; height:22px; background:var(--border-2);">

    {% if sensor.is_pos %}
    <!-- POSITIVE bar: starts at center (left:50%), extends RIGHT (coral) -->
    <div style="position:absolute; left:50%; top:0; height:100%;
                background:var(--coral); opacity:0.85;
                width:{{ sensor.pct|floatformat:2 }}%;
                transition:width 0.8s ease;">
    </div>
    {% else %}
    <!-- NEGATIVE bar: starts at center (right:50%), extends LEFT (green) -->
    <div style="position:absolute; right:50%; top:0; height:100%;
                background:var(--green-2); opacity:0.85;
                width:{{ sensor.pct|floatformat:2 }}%;
                transition:width 0.8s ease;">
    </div>
    {% endif %}

    <!-- Center line: 1px vertical line at exactly 50% -->
    <div style="position:absolute; left:50%; top:0; width:1px; height:100%;
                background:var(--border);">
    </div>

  </div>

  <!-- Numeric SHAP value on the right -->
  <span style="font-family:'DM Mono'; font-size:13px; min-width:60px; text-align:right;
               font-weight:600;
               color:{% if sensor.is_pos %}var(--coral){% else %}var(--green-2){% endif %};">
    {% if sensor.is_pos %}+{% endif %}{{ sensor.value|floatformat:5 }}
    <!--  "+0.03241"  or  "-0.01543"  -->
  </span>

</div>
```

---

## How Bar Positioning Works

The bar track `<div>` uses `position:relative`. Both the bar and center line are `position:absolute` inside it.

**Positive bar (failure direction):**
```css
position: absolute;
left: 50%;      /* starts at center */
width: 44.6%;   /* extends RIGHT by pct% */
background: var(--coral);
```

**Negative bar (healthy direction):**
```css
position: absolute;
right: 50%;     /* anchored to right side of center */
width: 23.8%;   /* extends LEFT by pct% */
background: var(--green-2);
```

**Center line:**
```css
position: absolute;
left: 50%;
width: 1px;     /* always 1px, always at center */
```

Visual result for a row:
```
[sensor_11         ] [░░░░░░░░░░░░░░░|████████████████░░░░░░░] +0.03241
[HPC Outlet Static ]                 ↑ center line
                     ←── green ──── | ──── coral ──→
```

---

## Value Display with `floatformat`

```django
{{ sensor.value|floatformat:5 }}
```
Django `floatformat:5` → always 5 decimal places. Example:
- `0.032410001` → `"0.03241"`
- `-0.01543` → `"-0.01543"`

The `+` sign for positive values is manually prepended:
```django
{% if sensor.is_pos %}+{% endif %}{{ sensor.value|floatformat:5 }}
```

---

## Transition Animation

```css
transition: width 0.8s ease;
```
When the page renders, bars animate from 0 to their final width over 0.8 seconds. This is pure CSS — no JavaScript required. It works because CSS transitions fire when the browser first paints the computed `width` value.

---

## Complete Data Example for 3 Sensors

| `sensor.id` | `sensor.name` | `sensor.value` | `sensor.is_pos` | `sensor.pct` | Bar direction |
|-------------|--------------|----------------|-----------------|-------------|---------------|
| `sensor_11` | HPC Outlet Static Pressure | `+0.03241` | `True` | `50.00` | → coral right |
| `sensor_4` | LPT Outlet Temperature | `+0.02891` | `True` | `44.59` | → coral right |
| `sensor_2` | LPC Outlet Temperature | `-0.01543` | `False` | `23.81` | ← green left |
| `sensor_9` | Physical Core Speed | `-0.00921` | `False` | `14.21` | ← green left |

---

## What Happens When SHAP API is Offline

If `shap_data` is `None`, the outer `{% if shap_data %}` block (line 183) prevents this entire section from rendering. Instead the "SHAP API Offline" fallback is shown (lines 516–571).
