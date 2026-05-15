# 27 — Explainability Page: Prediction Result Panel

**Source file:** `fl_shap_dashboard/templates/pages/explainability.html` (lines 183–303)  
**Context variables used:** `shap_data`, `selected_scenario`  
**Condition to render:** `{% if shap_data %}` — entire block hidden if SHAP API is offline

---

## What It Does
A 3-column card strip directly below the engine fleet selector. It shows the model's output for the currently selected engine and scenario:
- **Column 1 (Verdict):** CRITICAL or HEALTHY label, plus actual dataset truth if in random mode
- **Column 2 (Confidence Score):** The raw percentage + progress bar
- **Column 3 (Est. Remaining Life):** Estimated engine cycles remaining

---

## Data Flow

```
SHAP API → POST /explain/demo
    ↓ returns SHAPResponse
views.py → multiplies confidence × 100, stores in shap_data
    ↓
template context: shap_data = {
    prediction:   "FAILURE" | "HEALTHY",
    confidence:   85.4  (already ×100),
    actual_label: "FAILURE" | "HEALTHY" | None,
    actual_rul:   18  (None for non-random),
    engine_id:    47,
    factory_name: "Factory Mumbai (FD001)"
}
    ↓
explainability.html renders {% if shap_data %} block
```

---

## Outer Container (line 192)

```html
<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:0;
            background:var(--card); margin-bottom:32px;
            box-shadow:0 2px 16px rgba(0,0,0,0.08);
            border:2px solid var(--border);">
```
Three equal columns, no gap (gap:0), shared 2px border. The `box-shadow` gives it a slight card lift.

---

## Column 1: Verdict Panel (lines 195–260)

This column has **two different layouts** depending on whether `shap_data.actual_label` is present (random scenario) or not (simulated scenarios).

### Layout A — Random Scenario (`actual_label` is present)

Shows both CNN prediction AND the real dataset truth side by side for comparison.

```html
{% if shap_data.actual_label %}
<div style="background:var(--card); padding:24px 28px; display:flex; flex-direction:column; justify-content:space-between;">
  
  <!-- CNN PREDICTION label -->
  <span style="color:#5B6BDF; font-size:9px; font-weight:700; letter-spacing:0.12em;">CNN PREDICTION</span>

  <!-- Big verdict word: CRITICAL or HEALTHY -->
  <span class="font-display" style="font-size:3.2rem; font-weight:800; line-height:1;
    color: {% if shap_data.prediction == 'FAILURE' %}var(--coral){% else %}var(--green-2){% endif %};">
    {% if shap_data.prediction == 'FAILURE' %}CRITICAL{% else %}HEALTHY{% endif %}
  </span>
  <!-- Note: API returns 'FAILURE' string, template displays 'CRITICAL' to end users -->

  <hr style="border:none; border-top:1px solid var(--border-2);">

  <!-- DATASET ACTUAL label -->
  <span style="color:var(--green-2); font-size:9px; font-weight:700;">DATASET ACTUAL</span>

  <!-- Actual label from RUL file -->
  <span class="font-display" style="font-size:3.2rem; font-weight:800;
    color: {% if shap_data.actual_label == 'FAILURE' %}var(--coral){% else %}var(--green-2){% endif %};">
    {{ shap_data.actual_label }}
  </span>

  <!-- RUL number beside actual label -->
  <span style="font-size:12px; color:var(--muted); font-weight:600;">
    RUL {{ shap_data.actual_rul }}
  </span>

  <!-- Confidence + Engine ID row -->
  <span>Confidence: {{ shap_data.confidence|floatformat:1 }}%</span>
  <span>Engine #{{ shap_data.engine_id|default:"N/A" }}</span>

  <!-- Match/Mismatch badge at bottom -->
  {% if shap_data.prediction == shap_data.actual_label %}
    <span style="background:var(--green-bg); border:1px solid var(--green-lt); color:var(--green-2);">
      PREDICTION CORRECT
    </span>
  {% else %}
    <span style="background:var(--coral-bg); border:1px solid var(--coral-lt); color:var(--coral);">
      PREDICTION MISMATCH
    </span>
  {% endif %}
</div>
{% endif %}
```

**Key mapping:**
| API value | Displayed as |
|-----------|-------------|
| `prediction = "FAILURE"` | **CRITICAL** (in coral) |
| `prediction = "HEALTHY"` | **HEALTHY** (in green) |
| `actual_label = "FAILURE"` | **FAILURE** (in coral) |
| `actual_label = "HEALTHY"` | **HEALTHY** (in green) |

The MATCH badge logic:
```django
{% if shap_data.prediction == shap_data.actual_label %}
  → green "PREDICTION CORRECT" badge
{% else %}
  → coral "PREDICTION MISMATCH" badge
{% endif %}
```

### Layout B — Simulated Scenarios (`actual_label` is None)

Shows only the model verdict + factory name (no ground truth comparison).

```html
{% else %}
  <span style="color:#5B6BDF;">ENGINE VERDICT</span>
  <span class="font-display" style="font-size:3.2rem; ...
    color: {% if shap_data.prediction == 'FAILURE' %}var(--coral){% else %}var(--green-2){% endif %};">
    {% if shap_data.prediction == 'FAILURE' %}CRITICAL{% else %}HEALTHY{% endif %}
  </span>
  <span>FACTORY SOURCE</span>
  <span>{{ shap_data.factory_name }}</span>   <!-- e.g. "Factory Mumbai (FD001)" -->
  <span>Confidence: {{ shap_data.confidence|floatformat:1 }}%</span>
  <span>Engine #{{ shap_data.engine_id|default:"N/A" }}</span>
{% endif %}
```

---

## Column 2: Confidence Score (lines 262–281)

```html
<div style="background:var(--card); padding:24px 28px; border-left:1px solid var(--border);">
  
  <span style="color:var(--gold); font-size:9px; font-weight:700;">CONFIDENCE SCORE</span>

  <!-- Big number -->
  <span class="font-display" style="font-size:3.2rem; font-weight:800; color:var(--ink);">
    {{ shap_data.confidence|floatformat:1 }}%
  </span>

  <!-- Progress bar track -->
  <div style="height:6px; background:var(--border-2); margin-top:16px;">
    <!-- Filled portion — width = confidence value -->
    <div style="height:100%;
      background: {% if shap_data.prediction == 'FAILURE' %}var(--coral){% else %}var(--green-2){% endif %};
      width: {{ shap_data.confidence|floatformat:0 }}%;
      transition: width 0.8s ease;">
    </div>
  </div>

  <span style="font-size:10px; color:var(--muted);">Threshold: 40% → maintenance recommended</span>
  
  <div style="font-size:11px; color:var(--muted); line-height:1.5;">
    <strong>How it works:</strong> The AI analyzes sensor vibrations and pressure over the
    last 30 cycles. This percentage is the model's confidence that the engine will suffer
    a critical failure very soon.
  </div>
</div>
```

**How the progress bar width is set:**
```django
width: {{ shap_data.confidence|floatformat:0 }}%
```
Django `floatformat:0` rounds to 0 decimal places. So `85.4` → `85` → `width:85%`.  
Color: coral if FAILURE, dark green if HEALTHY.  
The `transition: width 0.8s ease` creates a smooth fill animation when the page loads.

**Note on threshold:** The SHAP API uses `FAILURE_THRESHOLD = 0.50` for the random scenario (50%), but the UI displays "40% → maintenance recommended" as the operator-facing threshold. This is intentional — operators should act before the model is fully certain.

---

## Column 3: Estimated Remaining Life (lines 283–301)

```html
<div style="background:var(--card); padding:24px 28px; border-left:1px solid var(--border);">
  
  <span style="color:#5B6BDF; font-size:9px; font-weight:700;">EST. REMAINING LIFE</span>

  <!-- The value is derived from prediction, NOT from actual_rul -->
  <span class="font-display" id="rul-value" style="font-size:3.2rem; font-weight:800;
    color: {% if shap_data.prediction == 'FAILURE' %}var(--coral){% else %}var(--green-2){% endif %};">
    {% if shap_data.prediction == 'FAILURE' %}
      &lt; 20
    {% else %}
      &gt; 80
    {% endif %}
  </span>

  <span style="font-size:10px; color:var(--muted);">engine cycles · act before 0</span>
</div>
```

**Important:** This is a **display approximation**, not the actual RUL value. The template just shows:
- `< 20` cycles (coral) if prediction is FAILURE
- `> 80` cycles (green) if prediction is HEALTHY

The real `actual_rul` (e.g., 18 cycles) is shown in Column 1 for the random scenario but is not used here. The element has `id="rul-value"` but no JavaScript currently updates it.

---

## Template Filter Used: `floatformat`

```django
{{ shap_data.confidence|floatformat:1 }}   → "85.4"   (1 decimal place)
{{ shap_data.confidence|floatformat:0 }}   → "85"     (used as CSS width %)
```

`shap_data.confidence` at this point is already multiplied × 100 by `views.py`.

---

## Visual Layout Summary

```
┌────────────────────────┬────────────────────────┬────────────────────────┐
│  CNN PREDICTION        │  CONFIDENCE SCORE      │  EST. REMAINING LIFE   │
│                        │                        │                        │
│  CRITICAL    ← coral  │  85.4%                 │  < 20                  │
│  ──────────────────── │  [████████░░░░░░░░░░]  │  engine cycles         │
│  DATASET ACTUAL        │  Threshold: 40%        │                        │
│  FAILURE  RUL 18      │                        │                        │
│                        │                        │                        │
│  [PREDICTION CORRECT]  │                        │                        │
└────────────────────────┴────────────────────────┴────────────────────────┘
         (random mode only)
```
