# views.py
import json
import requests
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from . import api_client

# In-memory cache for static SHAP scenarios — persists for the Django process lifetime
_SHAP_CACHE = {}

@login_required
def overview(request):
    """
    Overview dashboard — shows real metrics and factory status.
    Both accuracy cards are sourced from round_summaries (written every round by server).
    """
    factories  = api_client.get_factories()
    metrics    = api_client.get_metrics()
    clusters   = api_client.get_clusters()
    history    = api_client.get_cluster_history()

    session_start = metrics.get('session_start')

    # Round summaries: one row per round, has both accuracy metrics
    summaries  = api_client.get_round_summaries(limit=25, since=session_start)
    all_rounds = api_client.get_rounds(limit=500, since=session_start)

    # Latest summary = this round's numbers
    latest_summary    = summaries[0] if summaries else None
    clustered_acc     = latest_summary['clustered_accuracy'] if latest_summary else None
    naive_global_acc  = latest_summary['naive_global']       if latest_summary else None
    clustering_active = latest_summary['clustering_fired']   if latest_summary else False

    # Populate chart data from summaries (reverse for ascending order)
    chart_data = []
    for s in reversed(summaries):
        chart_data.append({
            'round':              s['round_num'],
            'clustered_accuracy': s['clustered_accuracy'],
            'naive_global':       s['naive_global'],
            'clustering_fired':   s['clustering_fired']
        })

    # Cluster state — only active if current session has fired clustering
    n_clusters = 0
    cluster_round = None
    if clustering_active:
        n_clusters = len([k for k in clusters.keys() if k != 'unassigned'])
        if history:
            cluster_round = history[-1]['round_num']

    # Latest 5 rounds for sidebar
    latest_5 = summaries[:5]


    context = {
        'ws_url':             'ws://localhost:8000/ws',
        'factories':          factories,
        'metrics':            metrics,
        # Two live accuracy values — both update every round
        'clustered_acc':      clustered_acc,
        'naive_global_acc':   naive_global_acc,
        # Keep latest_acc for any template parts that still reference it
        'latest_acc':         clustered_acc,
        'chart_data':         chart_data,
        'chart_data_json':    json.dumps(chart_data),
        'clusters_json':      json.dumps(clusters),
        'cluster_round':      cluster_round,
        'latest_5':           latest_5,
        'total_rounds':       metrics.get('total_rounds', 0),
        'n_clusters':         n_clusters,
        'active_page':        'overview',
    }
    return render(request, 'pages/overview.html', context)


@login_required
def simulation(request):
    factories = api_client.get_factories()
    metrics   = api_client.get_metrics()
    return render(request, 'pages/simulation.html', {
        'factories': factories,
        'metrics':   metrics,
        'ws_url':    'ws://localhost:8000/ws',
        'active_page': 'simulation',
    })


@login_required
def rounds(request):
    factory_id = request.GET.get('factory_id')
    algorithm  = request.GET.get('algorithm')

    all_rounds  = api_client.get_rounds(
        factory_id=factory_id, limit=200
    )
    factories   = api_client.get_factories()
    total_count = len(all_rounds)

    # Filter by algorithm if requested
    if algorithm:
        all_rounds = [r for r in all_rounds
                      if r['algorithm'] == algorithm]

    # Add factory name to each round
    factory_map = {f['factory_id']: f['name'] for f in factories}
    for r in all_rounds:
        r['factory_name'] = factory_map.get(r['factory_id'],
                                             f"Factory {r['factory_id']}")
        r['accuracy_pct'] = round(r['accuracy'] * 100, 1)
        r['cluster_label'] = (f"Cluster {r['cluster_id']}"
                              if r['cluster_id'] is not None
                              else "—")
        r['acc_color'] = (
            'text-green-600' if r['accuracy'] >= 0.85 else
            'text-amber-600' if r['accuracy'] >= 0.70 else
            'text-red-600'
        )

    return render(request, 'pages/rounds.html', {
        'rounds':       all_rounds[:100],
        'factories':    factories,
        'total_count':  total_count,
        'factory_id':   factory_id,
        'algorithm':    algorithm,
        'active_page':  'rounds',
    })


@login_required
def factories(request):
    factories_data = api_client.get_factories()
    clusters       = api_client.get_clusters()

    # Add color and accuracy display to each factory
    colors = {1: 'blue', 2: 'purple', 3: 'teal', 4: 'purple'}
    for f in factories_data:
        f['color'] = colors.get(f['factory_id'], 'blue')
        f['cluster_label'] = (f"Cluster {f['cluster_id']}"
                              if f['cluster_id'] is not None
                              else "Unassigned")

    return render(request, 'pages/factories.html', {
        'factories': factories_data,
        'clusters':  clusters,
        'active_page': 'factories',
    })


@login_required
def factory_detail(request, factory_id):
    factory = api_client.get_factory(factory_id)
    if not factory:
        from django.http import Http404
        raise Http404("Factory not found")

    rounds = factory.get('recent_rounds', [])
    for r in rounds:
        r['accuracy_pct'] = round(r['accuracy'] * 100, 1)

    return render(request, 'pages/factory_detail.html', {
        'factory':    factory,
        'rounds':     rounds,
        'chart_data': [{'round': r['round_num'],
                        'accuracy': r['accuracy']}
                       for r in reversed(rounds)],
        'active_page': 'factories',
    })


@login_required
def explainability(request):
    factories  = api_client.get_factories()
    factory_id = int(request.GET.get('factory_id', 1))
    scenario   = request.GET.get('scenario', 'critical')

    # In-memory cache for static scenarios (critical/healthy/degraded never change)
    # 'random' always fetches fresh data.
    # If 't' (timestamp) param is present the caller wants a fresh pick too — skip cache.
    cache_key = f"{factory_id}:{scenario}"
    force_fresh = bool(request.GET.get('t'))

    shap_data = None
    if scenario != 'random' and not force_fresh and cache_key in _SHAP_CACHE:
        shap_data = _SHAP_CACHE[cache_key]
    else:
        try:
            response = requests.post(
                "http://localhost:8001/explain/demo",
                params={"factory_id": factory_id, "scenario": scenario},
                timeout=10
            )
            if response.status_code == 200:
                shap_data = response.json()
                if 'confidence' in shap_data:
                    shap_data['confidence'] = round(shap_data['confidence'] * 100, 1)
                # Cache only static scenarios
                if scenario != 'random':
                    _SHAP_CACHE[cache_key] = shap_data
        except Exception as e:
            print(f"SHAP API offline: {e}")

    SENSOR_NAMES = {
        'sensor_1':  'Fan Inlet Temperature',
        'sensor_2':  'LPC Outlet Temperature',
        'sensor_3':  'HPC Outlet Temperature',
        'sensor_4':  'LPT Outlet Temperature',
        'sensor_5':  'Fan Inlet Pressure',
        'sensor_6':  'Bypass Duct Pressure',
        'sensor_7':  'HPC Outlet Pressure',
        'sensor_8':  'Physical Fan Speed',
        'sensor_9':  'Physical Core Speed',
        'sensor_10': 'Engine Pressure Ratio',
        'sensor_11': 'HPC Outlet Static Pressure',
        'sensor_12': 'Fuel-to-PS30 Ratio',
        'sensor_13': 'Corrected Fan Speed',
        'sensor_14': 'Corrected Core Speed',
        'sensor_15': 'Bypass Ratio',
        'sensor_16': 'Burner Fuel-Air Ratio',
        'sensor_17': 'Bleed Enthalpy',
        'sensor_18': 'Required Fan Speed',
        'sensor_19': 'Required Fan Conv Speed',
        'sensor_20': 'High-Pres Turbine Cool Flow',
        'sensor_21': 'Low-Pres Turbine Cool Flow',
    }
    
    # Process the shap data to be template-friendly
    template_shap_list = []
    template_top_list = []
    if shap_data:
        max_abs = max([abs(v) for v in shap_data['shap_values'].values()]) if shap_data['shap_values'] else 1.0
        for sensor, value in shap_data['shap_values'].items():
            pct = min((abs(value) / max_abs) * 50, 50)
            template_shap_list.append({
                'id': sensor,
                'name': SENSOR_NAMES.get(sensor, sensor),
                'value': value,
                'is_pos': value >= 0,
                'pct': pct
            })
            
        for idx, sensor in enumerate(shap_data['top_sensors']):
            label = "primary" if idx == 0 else ("secondary" if idx == 1 else "tertiary")
            
            # Generate deterministic sparkline points based on scenario
            points = []
            import random
            random.seed(42 + idx) # deterministic
            if scenario == 'critical':
                for i in range(30): points.append(0.5 + (i/30)*0.4 + (random.random()*0.1 - 0.05))
            elif scenario == 'degraded':
                for i in range(30): points.append(0.3 + (i/30)*0.2 + (random.random()*0.08 - 0.04))
            else:
                for i in range(30): points.append(0.15 + (random.random()*0.1 - 0.05))
            
            points = [min(max(p, 0), 1) for p in points]
            
            # Build SVG polyline string (W=200, H=60)
            pts_str = " ".join([f"{(i/29)*200},{60 - p*60}" for i, p in enumerate(points)])
            last_pt = points[-1]
            last_y = 60 - last_pt * 60
            
            template_top_list.append({
                'id': sensor,
                'name': SENSOR_NAMES.get(sensor, sensor),
                'label': label,
                'index': idx + 1,
                'pts_str': pts_str,
                'last_y': last_y,
                'last_pct': round(last_pt * 100, 1),
                'is_pos': shap_data['shap_values'].get(sensor, 0) >= 0
            })

    # Process rich metadata for the random scenario (dataset traceability)
    raw_sensor_rows = []
    if shap_data and shap_data.get('raw_sensor_sample'):
        for sensor, val in shap_data['raw_sensor_sample'].items():
            raw_sensor_rows.append({
                'id': sensor,
                'name': SENSOR_NAMES.get(sensor, sensor),
                'value': val,
            })

    # Load dataset validation proof if it exists
    import os, json
    validation_data = None
    json_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'validation_results.json')
    try:
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                validation_data = json.load(f)
    except Exception as e:
        print(f"Could not load validation JSON: {e}")

    return render(request, 'pages/explainability.html', {
        'factories':           factories,
        'selected_factory_id': factory_id,
        'selected_scenario':   scenario,
        'shap_data':           shap_data,
        'shap_list':           template_shap_list,
        'top_list':            template_top_list,
        'validation_data':     validation_data,
        'raw_sensor_rows':     raw_sensor_rows,
        'active_page':         'explain',
    })



@login_required
def topology(request):
    """
    FedSim Topology page — cluster graph + metrics panel.
    New page; does NOT modify any existing view or route.
    """
    factories = api_client.get_factories()
    metrics   = api_client.get_metrics()
    clusters  = api_client.get_clusters()
    history   = api_client.get_cluster_history()
    all_rounds = api_client.get_rounds(limit=500)

    # Build chart data (weighted accuracy per round)
    round_data = {}
    for r in all_rounds:
        rn = r['round_num']
        round_data.setdefault(rn, []).append(r)

    chart_data = []
    for rn in sorted(round_data.keys()):
        rlist = round_data[rn]
        total = sum(r['n_samples'] for r in rlist)
        avg   = sum(r['accuracy'] * r['n_samples'] for r in rlist) / total if total > 0 else 0
        chart_data.append({'round': rn, 'accuracy': round(avg, 4)})

    # Compute global accuracy from latest round
    latest_acc  = chart_data[-1]['accuracy'] if chart_data else None
    best_round  = max((d['round'] for d in chart_data), default=None)
    total_nodes = sum(len(v) for k, v in clusters.items())
    n_clusters  = len([k for k in clusters if k != 'unassigned'])
    latest_round_num = max(round_data.keys(), default=0) if round_data else 0

    # Synthesise recent events from cluster history
    events = []
    for h in reversed((history or [])[-8:]):
        events.append({
            'text':       f"Cluster {h.get('cluster_id','?')} updated — round {h.get('round_num','?')}",
            'cluster_id': h.get('cluster_id'),
            'timestamp':  h.get('timestamp'),
        })
    if not events and chart_data:
        events.append({
            'text':       f"Round {latest_round_num} completed",
            'cluster_id': None,
            'timestamp':  None,
        })

    context = {
        'ws_url':      'ws://localhost:8000/ws',
        'clusters_json':    json.dumps(clusters),
        'metrics_json':     json.dumps(metrics),
        'chart_data_json':  json.dumps(chart_data),
        'events_json':      json.dumps(events),
        'sim_info_json':    json.dumps({
            'round':        latest_round_num,
            'total_rounds': metrics.get('total_rounds', 500),
            'nodes':        total_nodes,
            'clusters':     n_clusters,
            'accuracy':     latest_acc,
            'convergence':  metrics.get('convergence_rate'),
            'status':       'Running',
        }),
        'active_page':      'topology',
    }
    return render(request, 'pages/topology.html', context)


# ── Live Factory Monitor ───────────────────────────────────────────

@login_required
def monitor(request):
    """Live Monitor page — renders the shell; JS polls /api/monitor/."""
    return render(request, 'pages/monitor.html', {
        'active_page': 'monitor',
    })


@login_required
def monitor_api(request):
    """JSON endpoint polled by the monitor page every N seconds."""
    from django.http import JsonResponse
    import random as rnd

    factory_id = int(request.GET.get('factory_id', rnd.randint(1, 4)))
    try:
        resp = requests.post(
            "http://localhost:8001/explain/demo",
            params={"factory_id": factory_id, "scenario": "random"},
            timeout=12,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Convert confidence to percentage
            data['confidence'] = round(data.get('confidence', 0) * 100, 1)
            data['factory_id'] = factory_id
            return JsonResponse({'ok': True, 'data': data})
        return JsonResponse({'ok': False, 'error': f'SHAP API returned {resp.status_code}'})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})