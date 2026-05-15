# 26 — Explainability Page: Engine Fleet Selector Cards

**Source file:** `fl_shap_dashboard/templates/pages/explainability.html` (lines 53–180)  
**JS functions:** `loadCard()`, `reloadAllCards()`, `shuffleEngine()`  
**API called:** `POST http://localhost:8001/explain/demo?factory_id=X&scenario=random`

---

## What It Does
Below the factory selector bar is a 4-column grid of clickable "engine cards". These let the user pick which engine prediction to display in the result panel below.

- **Card 1 (Random Engine):** Always calls the SHAP API live, picks a random engine from the real NASA test dataset, shows its prediction color-coded in real time.
- **Cards 2, 3, 4 (Slot 01/02/03):** Also call the SHAP API live on page load — each fetches a different random engine. Clicking one reloads the page with that engine's data as the main result.

---

## Data Flow

```
Page loads in browser
    ↓
window.addEventListener('DOMContentLoaded', reloadAllCards)
    ↓
reloadAllCards() calls loadCard() 3 times (staggered 300ms apart)
    ↓  (each call)
fetch POST http://localhost:8001/explain/demo?factory_id=FID&scenario=random
    ↓
SHAP API picks random engine from test_FD00X.txt
    ↓
Returns: { engine_id, prediction, confidence, actual_rul, dataset_file, ... }
    ↓
loadCard() updates card DOM: name, meta text, dot color, border color, href
```

For the "Random Engine" button:
```
User clicks "Random Engine"
    ↓
shuffleEngine() runs
    ↓
window.location.href = '?factory_id=FID&scenario=random&t=' + Date.now()
    ↓
Full page reload → views.py fetches fresh SHAP result (force_fresh=True because 't' param present)
    ↓
Result panel below updates with new engine
```

---

## HTML: Section Container (lines 53–66)

```html
<div style="background:var(--card); padding:24px 28px; border:1.5px solid var(--border); margin-bottom:32px;">
  
  <!-- Header row -->
  <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:18px;">
    <div>
      <span style="font-family:'DM Mono',monospace; font-size:9px; font-weight:700;">[ SELECT PREDICTION INSTANCE ]</span>
      <p>Choose an engine profile — Random picks a live engine from the NASA CMAPSS test dataset</p>
    </div>
    <!-- LIVE badge — only shown in random scenario -->
    {% if selected_scenario == 'random' %}
    <span style="background:#5B6BDF; color:white; ...">LIVE · test_FD00{{ selected_factory_id }}.txt</span>
    {% endif %}
  </div>

  <!-- 4-column grid -->
  <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px;">
    <!-- Card 1: Random Engine button -->
    <!-- Cards 2, 3, 4: Dynamic slots -->
  </div>
</div>
```

---

## Card 1: "Random Engine" Button (lines 70–91)

This is a `<button>` (not `<a>`), so it does NOT navigate by href — it calls `shuffleEngine()`.

```html
<button onclick="shuffleEngine()" type="button"
   style="display:flex; flex-direction:column; padding:14px 16px; cursor:pointer; width:100%;
     background: {% if selected_scenario == 'random' %}#F0F4FF{% else %}var(--bg){% endif %};
     border: 2px solid {% if selected_scenario == 'random' %}#5B6BDF{% else %}var(--border){% endif %};">
  
  <!-- Header: shuffle icon + "Random Engine" label + "REAL DATA" badge -->
  <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
    <div style="display:flex; align-items:center; gap:8px;">
      <!-- SVG shuffle icon (two crossing arrows) -->
      <svg width="16" height="16" ...><polyline .../><line .../></svg>
      <span class="font-display" style="font-size:13px; font-weight:700;">Random Engine</span>
    </div>
    <span style="background:#5B6BDF; color:white; ...">REAL DATA</span>
  </div>

  <span style="font-size:11px; color:var(--muted);">Live from NASA CMAPSS test set</span>
  <span style="font-family:'DM Mono'; font-size:9px; color:#5B6BDF;">
    test_FD00{{ selected_factory_id }}.txt
  </span>

  <!-- Bottom action label -->
  <div style="margin-top:auto; display:flex; align-items:center; gap:6px;">
    <span style="width:6px; height:6px; border-radius:50%; background:#5B6BDF;"></span>
    <span style="font-family:'DM Mono'; font-size:9px; color:#5B6BDF; font-weight:600;">
      CLICK TO PREDICT NEW ENGINE
    </span>
  </div>
</button>
```

**Active state:** When `selected_scenario == 'random'`, the card gets a light blue (`#F0F4FF`) background and a `#5B6BDF` border. Otherwise it's neutral.

---

## Cards 2, 3, 4: Dynamic Slots (lines 94–134)

All three slots share the same structure. They start empty with placeholder text and are filled dynamically by `loadCard()` JavaScript.

**Slot 01 HTML (representative, lines 94–106):**
```html
<a id="card-s1" href="#"
   style="display:flex; flex-direction:column; padding:14px 16px; text-decoration:none;
          background:var(--bg); border:1.5px solid var(--border); min-height:110px;">
  
  <!-- Name row: engine name (updates via JS) + SLOT badge -->
  <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
    <span id="s1-name" class="font-display" style="font-size:13px; font-weight:700; color:var(--ink);">
      Loading…
    </span>
    <span style="background:var(--coral); color:white; font-size:8px; padding:2px 6px;">SLOT 01</span>
  </div>

  <!-- Meta text: dataset · RUL · confidence% -->
  <span id="s1-meta" style="font-size:11px; color:var(--muted);">Fetching from CMAPSS…</span>

  <!-- Bottom: colored dot + prediction label -->
  <div style="margin-top:auto; display:flex; align-items:center; gap:6px;">
    <span id="s1-dot" style="width:6px; height:6px; border-radius:50%; background:var(--border);"></span>
    <span id="s1-pred" style="font-family:'DM Mono'; font-size:9px; font-weight:600; color:var(--muted);">...</span>
  </div>
</a>
```

**Slot badge colors:**
| Slot | Badge Color |
|------|------------|
| SLOT 01 | `var(--coral)` (orange-red) |
| SLOT 02 | `var(--gold)` (amber) |
| SLOT 03 | `#146B3A` (dark green) |

**All dynamic element IDs:**
| Element | Slot 1 ID | Slot 2 ID | Slot 3 ID | Updated by |
|---------|-----------|-----------|-----------|------------|
| Card `<a>` | `card-s1` | `card-s2` | `card-s3` | `card.href`, `card.style.borderColor`, `card.style.background` |
| Engine name | `s1-name` | `s2-name` | `s3-name` | `.textContent = 'Engine #' + d.engine_id` |
| Meta text | `s1-meta` | `s2-meta` | `s3-meta` | `.textContent = dataset + RUL + confidence` |
| Status dot | `s1-dot` | `s2-dot` | `s3-dot` | `.style.background = color` |
| Prediction | `s1-pred` | `s2-pred` | `s3-pred` | `.textContent = 'FAILURE PREDICTED' or 'HEALTHY PREDICTED'` |

---

## JavaScript: `loadCard()` (lines 142–165)

Called once per slot on page load. Makes a live POST to the SHAP API and populates the slot with real data.

```javascript
var FID = {{ selected_factory_id }};  // Django injects the current factory ID (1–4)

function loadCard(cardId, nameId, metaId, dotId, predId) {
  var card = document.getElementById(cardId);
  
  // Cache-bust with timestamp + random offset so each slot gets a different engine
  var t = Date.now() + Math.floor(Math.random() * 99999);
  
  fetch(
    'http://localhost:8001/explain/demo?factory_id=' + FID + '&scenario=random&_t=' + t,
    { method: 'POST' }
  )
  .then(function(r) { return r.json(); })
  .then(function(d) {
    var isFail = (d.prediction === 'FAILURE');
    var color  = isFail ? 'var(--coral)' : 'var(--green-2)';
    var bg     = isFail ? 'var(--coral-bg)' : 'var(--green-bg)';

    // Update engine name
    document.getElementById(nameId).textContent = 'Engine #' + d.engine_id;

    // Update meta line: "test_FD001.txt  ·  RUL 45  ·  78% confidence"
    document.getElementById(metaId).textContent =
      (d.dataset_file || 'test_FD00X') + '  ·  RUL ' + d.actual_rul +
      '  ·  ' + (d.confidence * 100).toFixed(0) + '% confidence';

    // Status dot color
    document.getElementById(dotId).style.background = color;

    // Prediction text
    document.getElementById(predId).textContent = isFail ? 'FAILURE PREDICTED' : 'HEALTHY PREDICTED';
    document.getElementById(predId).style.color = color;

    // Card border and background color
    card.style.borderColor = color;
    card.style.background  = bg;

    // Set href so clicking the card loads THIS engine as the main result
    card.href = '?factory_id=' + FID + '&scenario=random&t=' + t;
  })
  .catch(function(e) { console.warn('Card load failed:', e); });
}
```

**What `d` (the SHAP API response) contains used here:**
```json
{
  "engine_id": 47,
  "prediction": "FAILURE",
  "confidence": 0.812,
  "actual_rul": 18,
  "dataset_file": "test_FD001.txt"
}
```

---

## JavaScript: `reloadAllCards()` (lines 168–172)

Calls `loadCard()` three times with 300ms stagger so the three API requests don't all fire simultaneously.

```javascript
function reloadAllCards() {
  loadCard('card-s1', 's1-name', 's1-meta', 's1-dot', 's1-pred');
  setTimeout(function() {
    loadCard('card-s2', 's2-name', 's2-meta', 's2-dot', 's2-pred');
  }, 300);
  setTimeout(function() {
    loadCard('card-s3', 's3-name', 's3-meta', 's3-dot', 's3-pred');
  }, 600);
}

window.addEventListener('DOMContentLoaded', reloadAllCards);
```

**Why the stagger?** The SHAP API `random` mode uses `random.choice(valid_engines)` — if three requests hit simultaneously with the same seed timing, they may return the same engine. The 300ms delay ensures a different `Date.now()` timestamp seed for each.

---

## JavaScript: `shuffleEngine()` (lines 174–177)

Called when the user clicks the "Random Engine" button.

```javascript
function shuffleEngine() {
  window.location.href = '?factory_id=' + FID + '&scenario=random&t=' + Date.now();
}
```

This does a **full page navigation** (not AJAX). The `t=` timestamp param tells the Django view to skip the cache (`force_fresh = bool(request.GET.get('t'))`), so a completely fresh engine is selected from the dataset every time.

---

## Complete Click Flow: "Random Engine" Button

```
1. User clicks "Random Engine" button
2. shuffleEngine() fires
3. window.location.href = '?factory_id=1&scenario=random&t=1715776523000'
4. Browser makes GET request to Django
5. views.py → explainability()
     factory_id = 1
     scenario = 'random'
     force_fresh = True  (because 't' param is present)
     → skips _SHAP_CACHE
     → calls POST http://localhost:8001/explain/demo?factory_id=1&scenario=random
     → SHAP API picks a random engine from test_FD001.txt
     → returns full SHAPResponse
6. views.py builds template_shap_list, template_top_list, raw_sensor_rows
7. Renders explainability.html with new engine data
8. Result panel below shows new verdict, confidence, SHAP bars
```

## Complete Click Flow: Slot Card (e.g., Slot 01)

```
1. loadCard() ran on page load → set card-s1.href = '?factory_id=1&scenario=random&t=1715776520123'
2. User clicks Slot 01 card (<a> element)
3. Browser navigates to that pre-set href
4. Same flow as above — that specific t= timestamp reproducibly selects same engine
   (because the SHAP API uses random.choice with default Python random state, not a fixed seed for random scenario)
```
