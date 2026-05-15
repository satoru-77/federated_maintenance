# 25 — Explainability Page: Factory Selector Bar

**Source file:** `fl_shap_dashboard/templates/pages/explainability.html` (lines 18–51)  
**Data source:** `context['factories']` from `views.py → def explainability()`  
**URL pattern:** `/explainability/?factory_id=X&scenario=Y`

---

## What It Does
The factory selector bar is a horizontal strip of 4 clickable tabs — one per factory. Clicking a tab reloads the page with the selected factory's model and dataset, while keeping the current scenario unchanged.

---

## Data Flow

```
PostgreSQL (factories table)
    ↓
FastAPI GET /factories
    ↓
api_client.get_factories()   [dashboard/api_client.py]
    ↓
views.py → explainability()  → context['factories']
    ↓
explainability.html → {% for f in factories %}
    ↓
Rendered as 4 <a> tabs in the browser
```

---

## HTML Structure (lines 18–51)

```html
<div style="background:var(--card); padding:24px 28px; border:1.5px solid var(--border); margin-bottom:24px;">
  
  <!-- Section label row -->
  <div style="margin-bottom:14px;">
    <span style="font-family:'DM Mono',monospace; font-size:9px; font-weight:700; ...">
      [ SELECT FACTORY MODEL & DATASET ]
      
      <!-- Conditional sub-label — only shown in random scenario -->
      {% if selected_scenario == 'random' %}
        <span style="color:#5B6BDF; ...">← Also controls which test dataset is used for Random Engine</span>
      {% endif %}
    </span>
  </div>

  <!-- 4-tab strip container — uses flexbox, no gap, shared border -->
  <div style="display:flex; align-items:stretch; gap:0; border:1.5px solid var(--border); overflow:hidden;">
    
    {% for f in factories %}
    <a href="?factory_id={{ f.factory_id }}&scenario={{ selected_scenario|default:'critical' }}"
       style="display:flex; flex-direction:column; ...
              background: {% if f.factory_id == selected_factory_id %}var(--green){% else %}var(--card){% endif %};
              color:      {% if f.factory_id == selected_factory_id %}white{% else %}var(--muted){% endif %};
              border-right: {% if not forloop.last %}1px solid var(--border){% else %}none{% endif %};">
      
      <!-- Dot + factory name row -->
      <div style="display:flex; align-items:center; gap:6px;">
        <span style="width:7px; height:7px; border-radius:50%; background:
          {% if f.factory_id == 1 %}var(--green)
          {% elif f.factory_id == 2 %}var(--coral)
          {% elif f.factory_id == 3 %}#5B6BDF
          {% else %}var(--gold){% endif %};"></span>
        <span style="font-family:'DM Mono',monospace; font-size:13px; font-weight:600;">{{ f.name }}</span>
      </div>

      <!-- Dataset file label below name -->
      <span style="font-family:'DM Mono',monospace; font-size:10px; margin-left:13px;">
        test_FD00{{ f.factory_id }}.txt
      </span>
    </a>
    {% endfor %}
    
  </div>
</div>
```

---

## Key Template Logic Explained

### 1. Active tab highlighting
```django
background: {% if f.factory_id == selected_factory_id %}var(--green){% else %}var(--card){% endif %}
```
`selected_factory_id` comes from `views.py`:
```python
factory_id = int(request.GET.get('factory_id', 1))
```
If the factory in the loop matches the URL param, it gets dark green background + white text. All others stay card-colored with muted text.

### 2. The `href` on each tab
```django
href="?factory_id={{ f.factory_id }}&scenario={{ selected_scenario|default:'critical' }}"
```
- Clicking a tab does a **full page GET request** — not AJAX.
- The scenario is **preserved** across factory changes. If you were on `scenario=random` and click Factory 2, you land on `?factory_id=2&scenario=random`.
- `|default:'critical'` fallback ensures a valid scenario even if the template variable is empty.

### 3. Colored status dot per factory
Each factory has a hardcoded color:
| Factory ID | Factory Name | Dot Color |
|------------|-------------|-----------|
| 1 | Factory Mumbai | `var(--green)` = `#0B5E38` |
| 2 | Factory Berlin | `var(--coral)` = `#E8521A` |
| 3 | Factory Detroit | `#5B6BDF` (indigo) |
| 4 | Factory Tokyo | `var(--gold)` = `#C99A2E` |

When a tab is active, an additional border is drawn on the dot:
```django
{% if f.factory_id == selected_factory_id %}border:1.5px solid rgba(255,255,255,0.5){% endif %}
```

### 4. Border between tabs
```django
border-right: {% if not forloop.last %}1px solid var(--border){% else %}none{% endif %}
```
`forloop.last` is a Django built-in. The last tab gets no right border to avoid a double border with the outer container.

### 5. Dataset label
```html
test_FD00{{ f.factory_id }}.txt
```
Hardcoded pattern. Factory 1 → `test_FD001.txt`, Factory 2 → `test_FD002.txt`, etc. This is informational only — it shows the user which NASA CMAPSS test file will be used for the Random Engine feature.

### 6. Random scenario sub-label
```django
{% if selected_scenario == 'random' %}
  <span>← Also controls which test dataset is used for Random Engine</span>
{% endif %}
```
Only visible when the user is in random mode. Reminds the user that switching factory also switches the real test dataset being sampled from.

---

## What `factories` List Contains
Each item in `context['factories']` is a dict from `GET /factories` (FastAPI):
```json
{
  "factory_id": 1,
  "name": "Factory Mumbai",
  "dataset": "FD001",
  "n_engines": 100,
  "cluster_id": 0,
  "alpha_value": 0.7,
  "status": "active"
}
```
The template only uses `factory_id` and `name`. The dataset label is constructed inline: `test_FD00{{ f.factory_id }}.txt`.

---

## Visual Result
```
[ SELECT FACTORY MODEL & DATASET ]

┌───────────────┬───────────────┬───────────────┬───────────────┐
│ ● F.Mumbai    │ ● F.Berlin    │ ● F.Detroit   │ ● F.Tokyo     │  ← active = green bg
│ test_FD001.txt│ test_FD002.txt│ test_FD003.txt│ test_FD004.txt│
└───────────────┴───────────────┴───────────────┴───────────────┘
       ACTIVE (dark green)     muted/card color tabs
```
