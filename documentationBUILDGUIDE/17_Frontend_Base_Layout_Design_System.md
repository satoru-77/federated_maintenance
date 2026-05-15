# 17 — Frontend: Base Layout & Design System (`base.html`)

**File:** `fl_shap_dashboard/templates/base.html`  
**Extends:** Nothing (this IS the base)  
**Extended by:** Every page template via `{% extends "base.html" %}`  
**Contains:** CSS design tokens, global nav, page loader bar, backend connection checker

---

## Design Language: Greptile-Inspired

The entire dashboard uses a Greptile-style design language:
- **Background:** `#E8EBE4` — warm gray-green with dot-grid texture
- **Primary green:** `#0B5E38` — dark forest green (buttons, logo, active states)
- **Accent coral:** `#E8521A` — orange-coral (highlights, warnings, active nav underline)
- **Fonts:** Space Grotesk (display/numbers) + DM Mono (labels/tags) + Inter (body)

---

## CSS Design Tokens (`:root` Custom Properties)

```css
:root {
  /* Backgrounds */
  --bg:       #E8EBE4;   /* page background — warm gray-green */
  --card:     #F4F5F1;   /* card surface */
  --cream:    #F4F5F1;
  --cream-2:  #EAEDE6;   /* table header, hover rows */

  /* Brand colors */
  --green:    #0B5E38;   /* dark green — logo, buttons */
  --green-2:  #146B3A;   /* button hover */
  --green-lt: #7AAE8E;   /* border color for green badges */
  --green-bg: #D8EAE0;   /* green badge background */
  --coral:    #E8521A;   /* primary accent — warnings, failures */
  --coral-lt: #F4A98A;   /* coral border */
  --coral-bg: #FCEAE2;   /* coral badge background */
  --gold:     #C99A2E;   /* amber tags */
  --pink:     #D94F8A;   /* pink tags */

  /* Text */
  --ink:    #1A1B17;     /* near-black body text */
  --muted:  #6B6E63;     /* table headers, secondary text */

  /* Borders */
  --border:   #D0D4CC;
  --border-2: #E0E3DC;
}
```

---

## Global Body Style — Dot-Grid Texture

```css
body {
  font-family: 'Inter', sans-serif;
  background-color: var(--bg);
  background-image: radial-gradient(circle, #BFC3BC 1px, transparent 1px);
  background-size: 22px 22px;   /* 22px grid spacing */
  color: var(--ink);
  min-height: 100vh;
}
```

The `radial-gradient` creates a dot at the intersection of every 22×22px cell — a subtle engineering graph-paper aesthetic without performance cost.

---

## Typography System

```css
/* Display: used for page titles, stat numbers */
.font-display  { font-family: 'Space Grotesk', sans-serif; }

/* Monospace: used for labels, table headers, buttons, tags */
.font-mono-dm  { font-family: 'DM Mono', monospace; }

/* Bracket-style label [ LABEL ] */
.tag-label {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--coral);    /* coral variant */
}
.tag-label-green { /* same but var(--green-2) */ }

/* Large stat numbers */
.stat-num {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 700;
  font-size: 2rem;
  line-height: 1;
  color: var(--ink);
}
```

---

## Cluster Badges

```css
.badge-cluster-0 { color: var(--green);  border-color: var(--green-lt);  background: var(--green-bg); }
.badge-cluster-1 { color: var(--coral);  border-color: var(--coral-lt);  background: var(--coral-bg); }
.badge-cluster-2 { color: #1D4ED8;       border-color: #93C5FD;          background: #EFF6FF; }
.badge-cluster-3 { color: #7C3AED;       border-color: #C4B5FD;          background: #F5F3FF; }
```

Usage: `<span class="badge-cluster-0">Cluster 0</span>` — green badge for cluster 0, coral for cluster 1.

---

## Navigation Bar

```html
<nav class="topnav">  <!-- background: #1B3A2D, sticky, z-index:100 -->
  <div style="max-width:1200px;margin:0 auto;padding:0 32px;
              display:flex;align-items:center;justify-content:space-between;height:52px;">

    <!-- Logo: coral square + SVG stack icon + "FedPredict" wordmark -->
    <a href="/">
      <div style="width:26px;height:26px;background:var(--coral);...">
        <svg><!-- layer stack icon --></svg>
      </div>
      <span style="font-family:'Space Grotesk';font-weight:700;color:#fff;">FedPredict</span>
    </a>

    <!-- Nav links (DM Mono, 10px, uppercase, coral underline when active) -->
    <div style="display:flex;align-items:center;gap:2px;">
      <a href="/monitor/"        class="nav-link {% block nav_monitor    %}{% endblock %}">Monitor</a>
      <a href="/"                class="nav-link {% block nav_overview   %}{% endblock %}">Training</a>
      <a href="/simulation/"     class="nav-link {% block nav_simulation %}{% endblock %}">Simulation</a>
      <a href="/rounds/"         class="nav-link {% block nav_rounds     %}{% endblock %}">Rounds</a>
      <a href="/factories/"      class="nav-link {% block nav_factories  %}{% endblock %}">Factories</a>
      <a href="/explainability/" class="nav-link {% block nav_explain    %}{% endblock %}">Predict</a>
    </div>

    <!-- Right: live indicator + logout -->
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="background:rgba(74,222,128,0.1);border:1px solid rgba(74,222,128,0.2);...">
        <div id="global-live-dot" class="live-dot"></div>
        <span id="global-live-text" style="color:#4ADE80;">LIVE</span>
      </div>
      <a href="{% url 'logout' %}">LOGOUT</a>
    </div>
  </div>
</nav>
```

**Active nav link pattern:** Each page template sets its block:
```django
{# overview.html #}
{% block nav_overview %}active{% endblock %}
```
This outputs `class="nav-link active"` for the Training link, applying the coral underline.

---

## Live Pulse Dot Animation

```css
.live-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: #4ADE80;           /* green = backend connected */
  animation: live-pulse 1.6s ease-in-out infinite;
}
@keyframes live-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.4; transform: scale(0.85); }
}
```

---

## Page Loader Bar

```html
<div id="page-loader" style="position:fixed;top:0;left:0;width:0%;height:3px;
  background:linear-gradient(90deg,var(--coral),#E8521A,#F4A98A);
  z-index:9999;transition:width 0.3s ease;box-shadow:0 0 8px rgba(232,82,26,0.6);">
</div>
```

```javascript
// Fills to 70% on any link click, fills to 100% on page load
document.addEventListener('click', function(e) {
  const a = e.target.closest('a[href]');
  if (!a) return;
  // skip hash links, external links, ctrl+click
  bar.style.width = '70%';
});
window.addEventListener('load', () => {
  bar.style.width = '100%';
  setTimeout(() => { bar.style.opacity = '0'; }, 200);
  setTimeout(() => { bar.style.width = '0%'; bar.style.opacity = '1'; }, 700);
});
```

---

## Backend Connection Checker

```javascript
function checkBackendConnection() {
  fetch('http://localhost:8000/factories')
    .then(r => {
      if (r.ok) {
        // Backend UP: green dot, "LIVE"
        dot.className  = 'live-dot';
        dot.style.background = 'var(--green-2)';
        txt.textContent = 'LIVE';
        txt.style.color = 'var(--green-2)';

        // Also update sim-status-box if it exists (simulation page)
        if (simBox) { simBox.style.background = 'var(--green-bg)'; ... }
      } else { throw new Error('Not OK'); }
    })
    .catch(() => {
      // Backend DOWN: coral dot, "OFFLINE"
      dot.style.background = 'var(--coral)';
      txt.textContent = 'OFFLINE';
      txt.style.color = 'var(--coral)';
    });
}

checkBackendConnection();
setInterval(checkBackendConnection, 3000);   // re-check every 3 seconds
```

**IDs involved:**
- `#global-live-dot` — the animated dot in the nav bar
- `#global-live-text` — "LIVE" / "OFFLINE" text
- `#sim-status-box` — optional, on simulation page only
- `#sim-status-dot`, `#sim-status-text` — optional sim status display

---

## Template Block Structure

```
base.html defines:
  {% block title %}          → page title (default: "FedPredict")
  {% block extra_head %}     → extra CSS/meta tags per page
  {% block nav_monitor %}    → outputs "active" if this page is Monitor
  {% block nav_overview %}   → outputs "active" if this page is Training/Overview
  {% block nav_simulation %} → outputs "active" if Simulation
  {% block nav_rounds %}     → outputs "active" if Rounds
  {% block nav_factories %}  → outputs "active" if Factories
  {% block nav_explain %}    → outputs "active" if Predict/Explainability
  {% block content %}        → main page content
  {% block extra_scripts %}  → page-specific JavaScript
```
