# 18 — Frontend: URL Routing & API Client (`urls.py` + `api_client.py`)

**Files:**  
- `fl_shap_dashboard/core/urls.py` — root URL config (Django project level)  
- `fl_shap_dashboard/dashboard/urls.py` — app-level URL patterns  
- `fl_shap_dashboard/dashboard/api_client.py` — HTTP client for FastAPI calls

---

## URL Routing — Two-Level Structure

Django resolves URLs in two levels: project root → app.

### Level 1: `core/urls.py` (Project Root)

```python
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/',  admin.site.urls),
    path('login/',  auth_views.LoginView.as_view(),  name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('',        include('dashboard.urls')),   # all other URLs → dashboard app
]
```

All non-auth, non-admin URLs are passed to `dashboard.urls` via `include()`.

### Level 2: `dashboard/urls.py` (App Level)

```python
from django.urls import path
from . import views

urlpatterns = [
    path('',                            views.overview,       name='overview'),
    path('simulation/',                 views.simulation,     name='simulation'),
    path('rounds/',                     views.rounds,         name='rounds'),
    path('factories/',                  views.factories,      name='factories'),
    path('factories/<int:factory_id>/', views.factory_detail, name='factory_detail'),
    path('explainability/',             views.explainability, name='explainability'),
    path('topology/',                   views.topology,       name='topology'),
    path('monitor/',                    views.monitor,        name='monitor'),
    path('api/monitor/',                views.monitor_api,    name='monitor_api'),
]
```

### Complete URL Table

| URL | View function | Name | Description |
|-----|--------------|------|-------------|
| `/` | `overview()` | `overview` | Training dashboard — stat cards + D3 chart |
| `/simulation/` | `simulation()` | `simulation` | FL control panel + event log |
| `/rounds/` | `rounds()` | `rounds` | Round-by-round log table + CSV export |
| `/factories/` | `factories()` | `factories` | All 4 factories list |
| `/factories/1/` | `factory_detail(1)` | `factory_detail` | Single factory detail + accuracy chart |
| `/explainability/` | `explainability()` | `explainability` | SHAP explainability panel |
| `/topology/` | `topology()` | `topology` | D3 force graph + clustering timeline |
| `/monitor/` | `monitor()` | `monitor` | Live monitor page (polling) |
| `/api/monitor/` | `monitor_api()` | `monitor_api` | JSON endpoint for monitor page AJAX |
| `/login/` | Django built-in | `login` | Login form |
| `/logout/` | Django built-in | `logout` | Session clear + redirect |
| `/admin/` | Django admin | — | Admin panel |

---

## `api_client.py` — HTTP Abstraction Layer

All calls to the FastAPI backend (port 8000) go through this file. Views never call `requests` directly.

### Base URL Configuration

```python
BASE_URL = getattr(settings, 'FL_API_URL', 'http://localhost:8000')
# Can be overridden in Django settings.py:
# FL_API_URL = 'http://fl-api:8000'  (for Docker deployment)
```

### `_get()` — Central Request Handler

```python
def _get(endpoint, params=None):
    """
    Make a GET request to FastAPI. Returns JSON or None on failure.
    Timeout: 5 seconds (FastAPI must respond within 5s or request is dropped)
    """
    try:
        response = requests.get(
            f"{BASE_URL}{endpoint}",
            params=params,
            timeout=5
        )
        response.raise_for_status()   # raises HTTPError for 4xx/5xx
        return response.json()
    except Exception as e:
        print(f"[API] GET {endpoint} failed: {e}")
        return None   # caller handles None gracefully
```

**Design pattern:** Returns `None` on any failure. Callers use `or []` / `or {}` defaults:
```python
def get_factories():
    res = _get("/factories") or []
    ...
```

This means the dashboard **never crashes** when the FastAPI backend is down — it just shows empty data.

### All API Client Functions

```python
def get_factories():
    """Return list of all factories sorted by factory_id."""
    res = _get("/factories") or []
    if isinstance(res, list):
        return sorted(res, key=lambda x: x.get('factory_id', 0))
    return res

def get_factory(factory_id):
    """Return one factory with recent_rounds list."""
    return _get(f"/factories/{factory_id}")

def get_rounds(factory_id=None, limit=100, since=None):
    """Return training rounds with optional filters."""
    params = {"limit": limit}
    if factory_id:  params["factory_id"] = factory_id
    if since:       params["since"] = since
    return _get("/rounds", params=params) or []

def get_clusters():
    """Return current cluster assignments: {"0": [...], "1": [...]}."""
    return _get("/clusters") or {}

def get_cluster_history():
    """Return list of all cluster assignment events."""
    return _get("/clusters/history") or []

def get_metrics():
    """Return session-scoped summary: total_rounds, active_factories, latest_accuracy."""
    return _get("/metrics") or {}

def get_experiments():
    """Return all FL experiment runs."""
    return _get("/experiments") or []

def get_round_summaries(limit=25, since=None):
    """Return per-round dual accuracy: clustered_accuracy + naive_global."""
    params = {"limit": limit}
    if since: params["since"] = since
    return _get("/round-summaries", params=params) or []
```

---

## View → API Client → FastAPI → Template Flow

```
Browser GET /
    ↓
Django routes to: views.overview()
    ↓
views.overview() calls:
    api_client.get_metrics()        → GET http://localhost:8000/metrics
    api_client.get_factories()      → GET http://localhost:8000/factories
    api_client.get_round_summaries()→ GET http://localhost:8000/round-summaries
    api_client.get_cluster_history()→ GET http://localhost:8000/clusters/history
    ↓
Django renders: templates/pages/overview.html with context dict
    ↓
Browser receives full HTML

Browser JS on page:
    new WebSocket('ws://localhost:8000/ws')
    → receives "round_complete" / "round_summary" events
    → updates charts without page reload
```

---

## Django Authentication

All dashboard views require login (`@login_required` decorator in `views.py`). The auth flow:

```
Browser GET /             (not logged in)
    ↓ Django redirects to
Browser GET /login/       (Django built-in LoginView)
    ↓ user submits credentials
POST /login/              → session created → redirect to /
    ↓
Browser GET /             (now logged in)
    ↓ views.overview() proceeds normally
```

Session data is stored in `fl_shap_dashboard/db.sqlite3` (Django's default session backend).

Logout:
```
Browser GET /logout/  (Django LogoutView)
    ↓
Session cleared → redirect to /login/
```

---

## Django Settings — Key Configs

Located in `fl_shap_dashboard/core/settings.py`:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',       # Django REST Framework
    'dashboard',            # our app
]

TEMPLATES = [{
    'DIRS': [BASE_DIR / 'templates'],   # templates/ at project root
    ...
}]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# REST Framework: allows session-based browser auth for API calls
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ]
}
```
