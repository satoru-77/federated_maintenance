# 11 — Backend: All REST Endpoints (`main.py` Part 2)

**File:** `fl_backend/backend/main.py` (routes section)  
**Base URL:** `http://localhost:8000`  
**Called by:** Django `api_client.py` + JavaScript `fetch()` on monitor/simulation pages

---

## GET `/` — Health Check

```python
@app.get("/")
def health_check():
    return {
        "status":    "ok",
        "service":   "FL Predictive Maintenance API",
        "timestamp": datetime.utcnow().isoformat()
    }
```

**Response:**
```json
{"status": "ok", "service": "FL Predictive Maintenance API", "timestamp": "2026-05-15T12:30:00"}
```

Used by `start_all.ps1` to verify the API is up before launching the FL training.

---

## GET `/factories` — All Factories

```python
@app.get("/factories")
def get_factories(db: Session = Depends(get_db)):
    factories = db.query(Factory).all()
    return [
        {
            "factory_id":  f.factory_id,   # 1, 2, 3, 4
            "name":        f.name,          # "Factory Mumbai"
            "dataset":     f.dataset,       # "FD001"
            "n_engines":   f.n_engines,     # 100
            "cluster_id":  f.cluster_id,    # None until round 10, then 0 or 1
            "alpha_value": f.alpha_value,   # None until personalization
            "status":      f.status,        # "active"
        }
        for f in factories
    ]
```

**Used by:** Django `factories` view, overview page factory status cards, WebSocket initial load.

**Example response:**
```json
[
  {"factory_id": 1, "name": "Factory Mumbai", "dataset": "FD001",
   "n_engines": 100, "cluster_id": 0, "alpha_value": 0.7, "status": "active"},
  {"factory_id": 2, "name": "Factory Berlin", "dataset": "FD002",
   "n_engines": 260, "cluster_id": 1, "alpha_value": 0.5, "status": "active"}
]
```

---

## GET `/factories/{factory_id}` — Single Factory + Recent Rounds

```python
@app.get("/factories/{factory_id}")
def get_factory(factory_id: int, db: Session = Depends(get_db)):
    f = db.query(Factory).filter(Factory.factory_id == factory_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Factory not found")

    rounds = (
        db.query(TrainingRound)
        .filter(TrainingRound.factory_id == factory_id)
        .order_by(TrainingRound.round_num.desc())
        .limit(20)     # last 20 rounds only
        .all()
    )

    return {
        "factory_id": f.factory_id, "name": f.name, "dataset": f.dataset,
        "n_engines": f.n_engines, "cluster_id": f.cluster_id,
        "alpha_value": f.alpha_value, "status": f.status,
        "recent_rounds": [
            {
                "round_num": r.round_num,
                "accuracy":  r.accuracy,
                "loss":      r.loss,
                "algorithm": r.algorithm,
                "timestamp": r.timestamp.isoformat()
            }
            for r in rounds
        ]
    }
```

**Used by:** Django `factory_detail` view → Chart.js accuracy line chart on `factory_detail.html`.

---

## GET `/factories/{factory_id}/alpha` — Personalization Alpha

```python
@app.get("/factories/{factory_id}/alpha")
def get_factory_alpha(factory_id: int, db: Session = Depends(get_db)):
    f = db.query(Factory).filter(Factory.factory_id == factory_id).first()
    return {
        "factory_id":           f.factory_id,
        "name":                 f.name,
        "alpha_value":          f.alpha_value,        # None or 0.1–0.9
        "has_personalization":  f.alpha_value is not None
    }
```

---

## GET `/rounds` — Training Round Log (Filterable)

```python
@app.get("/rounds")
def get_rounds(
    factory_id: Optional[int] = None,   # ?factory_id=1
    limit:      int            = 100,    # ?limit=50
    since:      Optional[str]  = None,   # ?since=2026-05-15T16:00:00
    db: Session = Depends(get_db)
):
    query = db.query(TrainingRound)
    if factory_id:
        query = query.filter(TrainingRound.factory_id == factory_id)
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query    = query.filter(TrainingRound.timestamp >= since_dt)
        except ValueError:
            pass   # ignore malformed timestamp, return all

    rounds = query.order_by(TrainingRound.round_num.desc()).limit(limit).all()
    return [
        {
            "round_num":  r.round_num,
            "factory_id": r.factory_id,
            "algorithm":  r.algorithm,
            "accuracy":   r.accuracy,
            "loss":       r.loss,
            "n_samples":  r.n_samples,
            "cluster_id": r.cluster_id,
            "timestamp":  r.timestamp.isoformat()
        }
        for r in rounds
    ]
```

**Used by:** Django `rounds` view → rounds log table + CSV export.  
**Django call example:** `GET /rounds?limit=100` → all rounds for table  
**Monitor page:** `GET /rounds?since=<timestamp>&limit=50` → polled every 3 seconds

---

## GET `/clusters` — Current Cluster Assignments

```python
@app.get("/clusters")
def get_clusters(db: Session = Depends(get_db)):
    factories = db.query(Factory).all()
    clusters  = {}
    for f in factories:
        cid = str(f.cluster_id) if f.cluster_id is not None else "unassigned"
        clusters.setdefault(cid, []).append({
            "factory_id": f.factory_id,
            "name":       f.name,
            "dataset":    f.dataset
        })
    return clusters
```

**Response before clustering fires:**
```json
{"unassigned": [
  {"factory_id": 1, "name": "Factory Mumbai", "dataset": "FD001"},
  {"factory_id": 2, "name": "Factory Berlin", "dataset": "FD002"},
  ...
]}
```

**Response after clustering:**
```json
{
  "0": [
    {"factory_id": 1, "name": "Factory Mumbai", "dataset": "FD001"},
    {"factory_id": 3, "name": "Factory Detroit", "dataset": "FD003"}
  ],
  "1": [
    {"factory_id": 2, "name": "Factory Berlin", "dataset": "FD002"},
    {"factory_id": 4, "name": "Factory Tokyo", "dataset": "FD004"}
  ]
}
```

**Used by:** Django `topology` view → D3.js force graph on topology page.

---

## GET `/clusters/history` — Cluster Change Log

```python
@app.get("/clusters/history")
def get_cluster_history(db: Session = Depends(get_db)):
    assignments = (
        db.query(ClusterAssignment)
        .order_by(ClusterAssignment.timestamp.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "round_num":        a.round_num,
            "factory_id":       a.factory_id,
            "cluster_id":       a.cluster_id,
            "silhouette_score": a.silhouette_score,
            "k_value":          a.k_value,
            "reason":           a.reason,
            "timestamp":        a.timestamp.isoformat()
        }
        for a in assignments
    ]
```

**Used by:** Django `topology` view → timeline list on topology page.

---

## GET `/round-summaries` — Dual Accuracy Per Round

```python
@app.get("/round-summaries")
def get_round_summaries(limit: int = 25, since: Optional[str] = None, ...):
    summaries = query.order_by(RoundSummary.round_num.desc()).limit(limit).all()
    return [
        {
            "round_num":          s.round_num,
            "clustered_accuracy": s.clustered_accuracy,   # local training acc
            "naive_global":       s.naive_global,         # global model eval acc
            "n_clients":          s.n_clients,
            "clustering_fired":   s.clustering_fired,
            "timestamp":          s.timestamp.isoformat()
        }
        for s in summaries
    ]
```

**Used by:** D3.js dual-line chart on overview page (both accuracy series).

---

## GET `/metrics` — Session-Scoped Summary Stats

```python
@app.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    # Key insight: find the CURRENT session's start time
    # A new session starts when round_num=1 is inserted
    session_start = (
        db.query(func.max(TrainingRound.timestamp))
        .filter(TrainingRound.round_num == 1)
        .scalar()
    )
    # → returns timestamp of the most recent round_num=1 entry
    # If DB has multiple runs, this scopes to the most recent one

    if session_start:
        unique_rounds = (
            db.query(TrainingRound.round_num)
            .filter(TrainingRound.timestamp >= session_start)
            .distinct()
            .count()
        )
        latest_round = (
            db.query(TrainingRound)
            .filter(TrainingRound.timestamp >= session_start)
            .order_by(TrainingRound.round_num.desc())
            .first()
        )
    else:
        unique_rounds = 0
        latest_round  = None

    active_factories = db.query(Factory).filter(Factory.status == 'active').count()

    return {
        "total_rounds":     unique_rounds,         # rounds in current session
        "active_factories": active_factories,      # always 4
        "latest_round_num": latest_round.round_num if latest_round else 0,
        "latest_accuracy":  latest_round.accuracy  if latest_round else None,
        "session_start":    session_start.isoformat() if session_start else None,
    }
```

**Used by:** Django `overview` view → stat cards (total rounds, active factories, latest accuracy).

**Why session-scoped?**  
Without scoping, running the system twice would show round counts of 40+ instead of 20. The `func.max(timestamp) WHERE round_num=1` finds when the most recent session began, filtering out stale data from previous runs.

---

## POST `/sim/inject` — Byzantine Attack Simulation

```python
@app.post("/sim/inject")
def inject_scenario(scenario: str):
    valid = ['new_factory', 'byzantine', 'recluster', 'drop_factory']
    if scenario not in valid:
        raise HTTPException(status_code=400, ...)

    if scenario == 'byzantine':
        # Write a flag file that client.py reads
        flag_path = os.path.join(..., "byzantine_flag.txt")
        with open(flag_path, "w") as f:
            f.write("3")   # Factory 3 will be the Byzantine attacker
    
    return {"status": "ok", "scenario": scenario}
```

**Byzantine injection chain:**
```
Dashboard button "Inject Byzantine" clicked
    ↓
POST http://localhost:8000/sim/inject?scenario=byzantine
    ↓
FastAPI writes byzantine_flag.txt with content "3"
    ↓
Factory 3 client calls get_parameters() next round
    ↓
if os.path.exists("byzantine_flag.txt"): multiply weights × 500 + 100
    ↓
Server's ByzantineDetector: cosine similarity → 0.02 < 0.5 → FLAGGED
    ↓
POST /ws/broadcast {"type": "byzantine_alert", "factory_id": 3}
    ↓
Dashboard: Factory 3 bubble turns red
```
