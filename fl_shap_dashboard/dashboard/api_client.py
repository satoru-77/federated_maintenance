# api_client.py
# All calls to Member 1's FastAPI go through here.
# Never call requests directly from views.py

import requests
from django.conf import settings

BASE_URL = getattr(settings, 'FL_API_URL', 'http://localhost:8000')


def _get(endpoint, params=None):
    """Make a GET request. Returns JSON or empty dict on failure."""
    try:
        response = requests.get(
            f"{BASE_URL}{endpoint}",
            params=params,
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[API] GET {endpoint} failed: {e}")
        return None


def get_factories():
    """Return list of all factories with status."""
    res = _get("/factories") or []
    if isinstance(res, list):
        return sorted(res, key=lambda x: x.get('factory_id', 0))
    return res


def get_factory(factory_id):
    """Return one factory with recent rounds."""
    return _get(f"/factories/{factory_id}")


def get_rounds(factory_id=None, limit=100, since=None):
    """Return training rounds, optionally filtered by factory and/or session start."""
    params = {"limit": limit}
    if factory_id:
        params["factory_id"] = factory_id
    if since:
        params["since"] = since
    return _get("/rounds", params=params) or []


def get_clusters():
    """Return current cluster assignments."""
    return _get("/clusters") or {}


def get_cluster_history():
    """Return history of cluster changes."""
    return _get("/clusters/history") or []


def get_metrics():
    """Return system metrics."""
    return _get("/metrics") or {}


def get_experiments():
    """Return all experiment runs."""
    return _get("/experiments") or []


def get_round_summaries(limit=25, since=None):
    """Return per-round summaries with both accuracy metrics (clustered + naive global)."""
    params = {"limit": limit}
    if since:
        params["since"] = since
    return _get("/round-summaries", params=params) or []