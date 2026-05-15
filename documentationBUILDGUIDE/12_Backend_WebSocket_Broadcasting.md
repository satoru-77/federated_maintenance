# 12 — Backend: Database Logger & WebSocket Broadcasting (`db_logger.py`)

**File:** `fl_backend/backend/db_logger.py`  
**Called by:** `server.py → aggregate_fit()` and `aggregate_evaluate()` after every FL round  
**Purpose:** Write FL results to PostgreSQL AND push live updates to dashboard browsers simultaneously

---

## Architecture: The Bridge Between FL and Dashboard

```
FLOWER SERVER PROCESS (port 8080)          FASTAPI PROCESS (port 8000)
─────────────────────────────────          ──────────────────────────────
aggregate_fit() completes
  → log_round(...)
    ─── writes to PostgreSQL ─────────────► training_rounds table
    ─── HTTP POST ────────────────────────► /ws/broadcast
                                             → manager.broadcast(event)
                                               → all browser WebSockets

aggregate_evaluate() completes
  → log_round_summary(...)
    ─── upsert to PostgreSQL ─────────────► round_summaries table
    ─── HTTP POST ────────────────────────► /ws/broadcast {"type": "round_summary"}
```

`db_logger.py` runs **inside the Flower server process** but communicates with FastAPI via HTTP (cross-process IPC pattern). All DB writes use their own `SessionLocal()` instances (not FastAPI's `Depends(get_db)` — that's for request-scoped sessions).

---

## `log_round()` — Per-Factory Round Logging

```python
def log_round(round_num, factory_id, algorithm, accuracy,
              loss, n_samples, cluster_id=None):
    db = SessionLocal()
    try:
        round_entry = TrainingRound(
            round_num  = round_num,
            factory_id = factory_id,
            algorithm  = algorithm,
            accuracy   = accuracy,
            loss       = loss,
            n_samples  = n_samples,
            cluster_id = cluster_id,   # None before round 10
            timestamp  = datetime.utcnow()
        )
        db.add(round_entry)
        db.commit()

        print(f"  [DB] Round {round_num} | Factory {factory_id} | "
              f"Acc={accuracy:.4f} | Loss={loss:.4f} | logged")

        _broadcast_round_event(round_num, factory_id, algorithm,
                               accuracy, loss, cluster_id)
    except Exception as e:
        print(f"  [DB ERROR] Failed to log round: {e}")
        db.rollback()
    finally:
        db.close()
```

**Called 4 times per round** (once per factory, inside `aggregate_fit()`'s result loop). Each call is synchronous — the FL server waits for the DB write + HTTP broadcast before processing the next factory.

---

## `_broadcast_round_event()` — Round WebSocket Event

```python
def _broadcast_round_event(round_num, factory_id, algorithm, accuracy, loss, cluster_id):
    try:
        event = {
            "type":       "round_complete",    # JS handler key
            "round_num":  round_num,
            "factory_id": factory_id,
            "algorithm":  algorithm,
            "accuracy":   round(accuracy, 4),  # 0.8321 (4 decimal places)
            "loss":       round(loss, 4),
            "cluster_id": cluster_id,
            "timestamp":  datetime.utcnow().isoformat()
        }
        requests.post(
            "http://localhost:8000/ws/broadcast",
            json    = event,
            timeout = 1     # ← critical: don't block FL training if dashboard is down
        )
    except Exception:
        pass   # silently skip — FL training must not stop for a dead dashboard
```

**Dashboard JS handler** (in `overview.html`):
```javascript
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    if (data.type === 'round_complete') {
        updateFactoryCard(data.factory_id, data.accuracy, data.round_num);
        addEventLog(`Round ${data.round_num} — Factory ${data.factory_id}: ${(data.accuracy*100).toFixed(1)}%`);
        refreshD3Chart();
    }
}
```

---

## `log_cluster_assignment()` — Clustering Event

```python
def log_cluster_assignment(round_num, factory_id, cluster_id,
                           silhouette_score, k_value, reason="plateau_detected"):
    db = SessionLocal()
    try:
        # 1. Update factories table with new cluster_id
        factory = db.query(Factory).filter(Factory.factory_id == factory_id).first()
        if factory:
            factory.cluster_id = cluster_id
            # → factories.cluster_id column updated
            # → GET /factories will now return cluster_id = 0 or 1

        # 2. Insert history row
        assignment = ClusterAssignment(
            round_num        = round_num,
            factory_id       = factory_id,
            cluster_id       = cluster_id,
            silhouette_score = silhouette_score,
            k_value          = k_value,
            reason           = reason,
            timestamp        = datetime.utcnow()
        )
        db.add(assignment)
        db.commit()

        _broadcast_cluster_event(round_num, factory_id, cluster_id,
                                 silhouette_score, k_value)
    except Exception as e:
        db.rollback()
    finally:
        db.close()
```

**Two writes in one transaction:**
1. `UPDATE factories SET cluster_id=X` — updates current state
2. `INSERT INTO cluster_assignments` — creates history record

---

## `_broadcast_cluster_event()` — Cluster WebSocket Event

```python
def _broadcast_cluster_event(round_num, factory_id, cluster_id,
                             silhouette_score, k_value):
    event = {
        "type":             "cluster_assigned",   # JS handler key
        "round_num":        round_num,
        "factory_id":       factory_id,
        "cluster_id":       cluster_id,
        "silhouette_score": round(silhouette_score, 4),
        "k_value":          k_value,
        "timestamp":        datetime.utcnow().isoformat()
    }
    requests.post("http://localhost:8000/ws/broadcast", json=event, timeout=1)
```

**Dashboard JS handler** (in `overview.html`):
```javascript
if (data.type === 'cluster_assigned') {
    updateClusterBubble(data.factory_id, data.cluster_id);
    addEventLog(`Cluster assigned: Factory ${data.factory_id} → Cluster ${data.cluster_id}`);
}
```

---

## `update_factory_alpha()` — Personalization Update

```python
def update_factory_alpha(factory_id, alpha_value):
    db = SessionLocal()
    try:
        factory = db.query(Factory).filter(Factory.factory_id == factory_id).first()
        if factory:
            factory.alpha_value = alpha_value
            db.commit()
            print(f"  [DB] Factory {factory_id} alpha={alpha_value} updated")
    except Exception as e:
        db.rollback()
    finally:
        db.close()
```

SQL equivalent: `UPDATE factories SET alpha_value = 0.7 WHERE factory_id = 1`

---

## `log_round_summary()` — Upsert Dual Accuracy

```python
def log_round_summary(round_num, clustered_accuracy, naive_global,
                      n_clients, clustering_fired=False):
    db = SessionLocal()
    try:
        existing = db.query(RoundSummary).filter(
            RoundSummary.round_num == round_num
        ).first()

        if existing:
            # UPDATE (round already exists — e.g. re-run of same round)
            existing.clustered_accuracy = clustered_accuracy
            existing.naive_global       = naive_global
            existing.n_clients          = n_clients
            existing.clustering_fired   = clustering_fired
            existing.timestamp          = datetime.utcnow()
        else:
            # INSERT
            db.add(RoundSummary(
                round_num          = round_num,
                clustered_accuracy = clustered_accuracy,
                naive_global       = naive_global,
                n_clients          = n_clients,
                clustering_fired   = clustering_fired,
                timestamp          = datetime.utcnow()
            ))
        db.commit()

        _broadcast_round_summary(round_num, clustered_accuracy, naive_global, clustering_fired)
    except Exception as e:
        db.rollback()
    finally:
        db.close()
```

**Why upsert?** `RoundSummary.round_num` is unique. If `aggregate_evaluate()` is called twice for the same round (Flower retry), the second call would fail with a unique constraint violation if we always INSERT. The check-and-update pattern handles this safely.

---

## `_broadcast_round_summary()` — Summary WebSocket Event

```python
def _broadcast_round_summary(round_num, clustered_accuracy, naive_global, clustering_fired):
    event = {
        "type":               "round_summary",      # JS handler key
        "round_num":          round_num,
        "clustered_accuracy": round(clustered_accuracy, 4) if clustered_accuracy else None,
        "naive_global":       round(naive_global, 4)       if naive_global       else None,
        "clustering_fired":   clustering_fired,
        "timestamp":          datetime.utcnow().isoformat()
    }
    requests.post("http://localhost:8000/ws/broadcast", json=event, timeout=1)
```

**Dashboard JS handler** (in `overview.html`):
```javascript
if (data.type === 'round_summary') {
    // Update D3 dual-line chart with both series
    d3Chart.addDataPoint(data.round_num, data.clustered_accuracy, data.naive_global);
    
    // Flash clustering indicator if just fired
    if (data.clustering_fired) {
        document.getElementById('clustering-badge').classList.add('active');
    }
}
```

---

## All WebSocket Event Types Summary

| `type` field | Fired by | Dashboard action |
|--------------|----------|-----------------|
| `round_complete` | `log_round()` × 4 per round | Update factory card, log line |
| `cluster_assigned` | `log_cluster_assignment()` × 4 | Move bubble to cluster, log line |
| `round_summary` | `log_round_summary()` × 1 per round | Update D3 dual chart |
| `byzantine_alert` | `server.py` directly | Turn factory bubble red |
| `pong` | `/ws` endpoint | Keepalive response to ping |

---

## Error Handling Pattern

Every function follows the same try/except/finally pattern:

```python
db = SessionLocal()     # create session (not request-scoped)
try:
    # ... DB operations ...
    db.commit()
except Exception as e:
    db.rollback()       # revert on any error
    print(f"[DB ERROR] ...")
finally:
    db.close()          # always close (prevents connection leaks)
```

The `requests.post()` calls are inside their own `try/except Exception: pass` blocks — a dead FastAPI process must never stop FL training.
