# 19 — Django Views: All View Functions (`views.py`)

**File:** `fl_shap_dashboard/dashboard/views.py`  
**All views protected by:** `@login_required` decorator  
**API calls go through:** `api_client.py` (never raw `requests` except SHAP API)

---

## `overview()` — Training Dashboard

```python
@login_required
def overview(request):
    factories  = api_client.get_factories()
    metrics    = api_client.get_metrics()
    clusters   = api_client.get_clusters()
    history    = api_client.get_cluster_history()

    session_start = metrics.get('session_start')
    # Scopes ALL subsequent queries to the current training session

    summaries  = api_client.get_round_summaries(limit=25, since=session_start)
    all_rounds = api_client.get_rounds(limit=500, since=session_start)

    latest_summary   = summaries[0] if summaries else None
    clustered_acc    = latest_summary['clustered_accuracy'] if latest_summary else None
    naive_global_acc = latest_summary['naive_global']       if latest_summary else None
    clustering_active= latest_summary['clustering_fired']   if latest_summary else False
```

**Chart data construction:**
```python
    chart_data = []
    for s in reversed(summaries):   # reverse = ascending round order
        chart_data.append({
            'round':              s['round_num'],
            'clustered_accuracy': s['clustered_accuracy'],
            'naive_global':       s['naive_global'],
            'clustering_fired':   s['clustering_fired']
        })
    # chart_data is passed as JSON to D3.js: {{ chart_data_json|safe }}
```

**Cluster state detection:**
```python
    n_clusters, cluster_round = 0, None
    if clustering_active:
        n_clusters  = len([k for k in clusters.keys() if k != 'unassigned'])
        cluster_round = history[-1]['round_num'] if history else None
```

**Context passed to template:**
```python
    context = {
        'ws_url':           'ws://localhost:8000/ws',
        'factories':        factories,
        'metrics':          metrics,
        'clustered_acc':    clustered_acc,     # shown in green card
        'naive_global_acc': naive_global_acc,  # shown in gray card
        'latest_acc':       clustered_acc,     # alias for legacy template refs
        'chart_data':       chart_data,
        'chart_data_json':  json.dumps(chart_data),  # embedded in JS
        'clusters_json':    json.dumps(clusters),     # embedded in Canvas JS
        'cluster_round':    cluster_round,
        'latest_5':         summaries[:5],     # sidebar round list
        'total_rounds':     metrics.get('total_rounds', 0),
        'n_clusters':       n_clusters,
    }
```

---

## `simulation()` — FL Control Panel

```python
@login_required
def simulation(request):
    factories = api_client.get_factories()
    metrics   = api_client.get_metrics()
    return render(request, 'pages/simulation.html', {
        'factories': factories,
        'metrics':   metrics,
        'ws_url':    'ws://localhost:8000/ws',
    })
```

Minimal view — the simulation page is mostly JavaScript-driven (buttons call `POST /sim/start`, `POST /sim/stop`, `POST /sim/inject` directly via `fetch()`).

---

## `rounds()` — Training Round Log

```python
@login_required
def rounds(request):
    factory_id = request.GET.get('factory_id')   # optional filter: ?factory_id=1
    algorithm  = request.GET.get('algorithm')    # optional filter: ?algorithm=FedAvg

    all_rounds = api_client.get_rounds(factory_id=factory_id, limit=200)
    if algorithm:
        all_rounds = [r for r in all_rounds if r['algorithm'] == algorithm]

    # Enrich each round row with display-friendly fields
    factory_map = {f['factory_id']: f['name'] for f in api_client.get_factories()}
    for r in all_rounds:
        r['factory_name'] = factory_map.get(r['factory_id'], f"Factory {r['factory_id']}")
        r['accuracy_pct'] = round(r['accuracy'] * 100, 1)
        r['cluster_label'] = f"Cluster {r['cluster_id']}" if r['cluster_id'] is not None else "—"
        r['acc_color'] = (
            'text-green-600' if r['accuracy'] >= 0.85 else
            'text-amber-600' if r['accuracy'] >= 0.70 else
            'text-red-600'
        )
    # Limit table to 100 rows to avoid slow rendering
    return render(request, 'pages/rounds.html', {'rounds': all_rounds[:100], ...})
```

---

## `factories()` — Factory List

```python
@login_required
def factories(request):
    factories_data = api_client.get_factories()
    clusters       = api_client.get_clusters()

    # Assign display colors per factory
    colors = {1: 'blue', 2: 'purple', 3: 'teal', 4: 'purple'}
    for f in factories_data:
        f['color'] = colors.get(f['factory_id'], 'blue')
        f['cluster_label'] = (
            f"Cluster {f['cluster_id']}" if f['cluster_id'] is not None else "Unassigned"
        )
```

---

## `factory_detail()` — Single Factory View

```python
@login_required
def factory_detail(request, factory_id):
    factory = api_client.get_factory(factory_id)   # GET /factories/{id} → includes recent_rounds
    if not factory:
        raise Http404("Factory not found")

    rounds = factory.get('recent_rounds', [])
    for r in rounds:
        r['accuracy_pct'] = round(r['accuracy'] * 100, 1)

    # Build chart_data in ascending round order (Chart.js expects this)
    chart_data = [{'round': r['round_num'], 'accuracy': r['accuracy']}
                  for r in reversed(rounds)]
```

---

## `explainability()` — SHAP Explanation Page

The most complex view. Handles factory/scenario selection, SHAP API calls, in-memory caching, sensor name mapping, sparkline generation, and raw sensor data display.

```python
# In-memory cache: {factory_id:scenario → SHAP response}
_SHAP_CACHE = {}

@login_required
def explainability(request):
    factory_id = int(request.GET.get('factory_id', 1))
    scenario   = request.GET.get('scenario', 'critical')
    force_fresh= bool(request.GET.get('t'))   # ?t=<timestamp> = bypass cache

    # Cache: static scenarios (healthy/degraded/critical) never change
    # Random scenario always fetches fresh — uses different engine each time
    cache_key = f"{factory_id}:{scenario}"
    if scenario != 'random' and not force_fresh and cache_key in _SHAP_CACHE:
        shap_data = _SHAP_CACHE[cache_key]
    else:
        response = requests.post(
            "http://localhost:8001/explain/demo",
            params={"factory_id": factory_id, "scenario": scenario},
            timeout=10
        )
        shap_data = response.json()
        shap_data['confidence'] = round(shap_data['confidence'] * 100, 1)  # 0.78 → 78.0
        if scenario != 'random':
            _SHAP_CACHE[cache_key] = shap_data   # cache only static
```

**Sensor name mapping (21 sensors → physical names):**
```python
    SENSOR_NAMES = {
        'sensor_2':  'LPC Outlet Temperature',
        'sensor_3':  'HPC Outlet Temperature',
        'sensor_7':  'HPC Outlet Pressure',
        'sensor_8':  'Physical Fan Speed',
        'sensor_9':  'Physical Core Speed',
        'sensor_11': 'HPC Outlet Static Pressure',
        'sensor_12': 'Fuel-to-PS30 Ratio',
        'sensor_14': 'Corrected Core Speed',
        'sensor_15': 'Bypass Ratio',
        'sensor_17': 'Bleed Enthalpy',
        'sensor_20': 'High-Pres Turbine Cool Flow',
        'sensor_21': 'Low-Pres Turbine Cool Flow',
        # ... all 21 sensors
    }
```

**SHAP list preparation (for waterfall chart):**
```python
    max_abs = max([abs(v) for v in shap_data['shap_values'].values()])
    for sensor, value in shap_data['shap_values'].items():
        pct = min((abs(value) / max_abs) * 50, 50)   # scale to max 50%
        template_shap_list.append({
            'id': sensor,
            'name': SENSOR_NAMES.get(sensor, sensor),
            'value': value,
            'is_pos': value >= 0,   # True = failure-direction (red bar)
            'pct': pct              # CSS width percentage
        })
```

**Sparkline generation (SVG polyline for top 3 sensors):**
```python
    random.seed(42 + idx)   # deterministic per sensor index
    if scenario == 'critical':
        # Rising trend: 0.5 + (i/30)*0.4 + noise → simulates degradation
        for i in range(30): points.append(0.5 + (i/30)*0.4 + (random.random()*0.1 - 0.05))
    elif scenario == 'degraded':
        # Moderate rising: 0.3 + (i/30)*0.2
    else:  # healthy
        # Flat: 0.15 + noise

    pts_str = " ".join([f"{(i/29)*200},{60 - p*60}" for i, p in enumerate(points)])
    # SVG polyline points string: "0,60 7,55 14,52 ..." (W=200, H=60)
```

---

## `topology()` — Cluster Force Graph

```python
@login_required
def topology(request):
    # Compute weighted accuracy per round from all individual round rows
    round_data = {}
    for r in all_rounds:
        round_data.setdefault(r['round_num'], []).append(r)

    chart_data = []
    for rn in sorted(round_data.keys()):
        rlist = round_data[rn]
        total = sum(r['n_samples'] for r in rlist)
        avg   = sum(r['accuracy'] * r['n_samples'] for r in rlist) / total
        chart_data.append({'round': rn, 'accuracy': round(avg, 4)})

    # Build recent events list from cluster history
    events = [
        {
            'text':       f"Cluster {h['cluster_id']} updated — round {h['round_num']}",
            'cluster_id': h['cluster_id'],
            'timestamp':  h['timestamp'],
        }
        for h in reversed((history or [])[-8:])
    ]
```

All data passed as JSON strings (`json.dumps()`) → embedded in D3.js and JavaScript on the topology page.

---

## `monitor()` + `monitor_api()` — Live Monitor

```python
@login_required
def monitor(request):
    """Shell page — JS polls /api/monitor/ every N seconds."""
    return render(request, 'pages/monitor.html', {'active_page': 'monitor'})

@login_required
def monitor_api(request):
    """JSON endpoint: picks a random factory, calls SHAP API, returns inference result."""
    factory_id = int(request.GET.get('factory_id', random.randint(1, 4)))
    resp = requests.post(
        "http://localhost:8001/explain/demo",
        params={"factory_id": factory_id, "scenario": "random"},
        timeout=12
    )
    data = resp.json()
    data['confidence'] = round(data.get('confidence', 0) * 100, 1)
    return JsonResponse({'ok': True, 'data': data})
```

The monitor page JS calls `fetch('/api/monitor/?factory_id=X')` every few seconds → displays rolling live inference results without full page reload.
