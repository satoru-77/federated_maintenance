# 02 — Database Schema: All Tables

**Files:** `fl_backend/backend/models.py`, `fl_backend/backend/db.py`  
**Database:** PostgreSQL (`fl_maintenance2`)  
**ORM:** SQLAlchemy (declarative base pattern)  
**Tables:** 6 — `factories`, `training_rounds`, `cluster_assignments`, `model_weights`, `experiments`, `round_summaries`

---

## 1. Database Connection (`db.py`)

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from .models import Base

load_dotenv()   # reads fl_backend/.env

DB_HOST = os.getenv('DB_HOST', 'localhost')       # default: localhost
DB_PORT = os.getenv('DB_PORT', '5432')            # default: PostgreSQL port
DB_NAME = os.getenv('DB_NAME', 'fl_maintenance')  # override: fl_maintenance2
DB_USER = os.getenv('DB_USER', 'fl_user')         # override: postgres
DB_PASS = os.getenv('DB_PASSWORD', 'fl_password_123')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
# Example: "postgresql://postgres:indra10@localhost:5432/fl_maintenance2"

engine       = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

### `create_tables()`
```python
def create_tables():
    """
    Creates all 6 tables if they don't already exist.
    Safe to call repeatedly — uses CREATE TABLE IF NOT EXISTS internally.
    Called once in main.py on FastAPI startup.
    """
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")
```

### `get_db()` — FastAPI Dependency
```python
def get_db():
    """
    Yields a database session per request.
    Automatically closes the session (even on exception) via finally block.
    Used in route functions as: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Usage in FastAPI routes:
```python
from fastapi import Depends
from sqlalchemy.orm import Session
from .db import get_db

@app.get("/factories")
def get_factories(db: Session = Depends(get_db)):
    return db.query(Factory).all()
```

---

## 2. Table: `factories`

**Class:** `Factory`  
**Purpose:** One row per factory — static info + current cluster/alpha status  
**Rows:** 4 (seeded at startup by `db_logger.py`)

```python
class Factory(Base):
    __tablename__ = 'factories'

    id          = Column(Integer, primary_key=True)      # auto-increment PK
    factory_id  = Column(Integer, unique=True, nullable=False)  # 1, 2, 3, 4
    name        = Column(String(100), nullable=False)    # "Factory Mumbai"
    dataset     = Column(String(10), nullable=False)     # "FD001"
    n_engines   = Column(Integer, nullable=False)        # 100, 260, 100, 248
    cluster_id  = Column(Integer, nullable=True)         # NULL until round 10
    alpha_value = Column(Float, nullable=True)           # NULL until personalization
    status      = Column(String(20), default='active')   # "active" | "disconnected"
    created_at  = Column(DateTime, default=datetime.utcnow)

    rounds = relationship('TrainingRound', back_populates='factory')
    # one-to-many: one factory has many training_rounds
```

**Sample data after seeding:**
```
id | factory_id | name              | dataset | n_engines | cluster_id | alpha_value | status
---+-----------+-------------------+---------+-----------+------------+-------------+-------
1  | 1         | Factory Mumbai    | FD001   | 100       | NULL       | NULL        | active
2  | 2         | Factory Berlin    | FD002   | 260       | NULL       | NULL        | active
3  | 3         | Factory Detroit   | FD003   | 100       | NULL       | NULL        | active
4  | 4         | Factory Tokyo     | FD004   | 248       | NULL       | NULL        | active
```

**After clustering fires at round 10:**
```
factory_id | cluster_id | alpha_value
-----------+------------+------------
1          | 0          | 0.7
2          | 1          | 0.5
3          | 0          | 0.8
4          | 1          | 0.6
```

---

## 3. Table: `training_rounds`

**Class:** `TrainingRound`  
**Purpose:** One row **per factory per FL round** — the primary data source for all dashboard charts  
**Rows after 20 rounds:** 80 (20 rounds × 4 factories)

```python
class TrainingRound(Base):
    __tablename__ = 'training_rounds'

    id         = Column(Integer, primary_key=True)
    round_num  = Column(Integer, nullable=False)      # 1, 2, 3 ... 20
    factory_id = Column(Integer, ForeignKey('factories.factory_id'))
    algorithm  = Column(String(20), nullable=False)   # "FedAvg" | "FedProx"
    accuracy   = Column(Float, nullable=False)         # 0.0 – 1.0
    loss       = Column(Float, nullable=False)         # CrossEntropy loss
    n_samples  = Column(Integer, nullable=False)       # training samples used
    cluster_id = Column(Integer, nullable=True)        # NULL before round 10
    timestamp  = Column(DateTime, default=datetime.utcnow)

    factory = relationship('Factory', back_populates='rounds')
```

**Sample rows:**
```
id | round_num | factory_id | algorithm | accuracy | loss   | n_samples | cluster_id | timestamp
---+-----------+------------+-----------+----------+--------+-----------+------------+-----------
1  | 1         | 1          | FedAvg    | 0.612    | 0.7821 | 17731     | NULL       | 16:10:04
2  | 1         | 2          | FedAvg    | 0.589    | 0.8102 | 46123     | NULL       | 16:10:05
3  | 1         | 3          | FedAvg    | 0.634    | 0.7544 | 21542     | NULL       | 16:10:06
4  | 1         | 4          | FedAvg    | 0.571    | 0.8334 | 54089     | NULL       | 16:10:07
...
77 | 20        | 1          | FedAvg    | 0.834    | 0.4102 | 17731     | 0          | 16:45:21
```

**Used by:**
- `GET /rounds` → rounds log page + CSV export
- `GET /factories/{id}` → factory detail chart
- `GET /metrics` → weighted accuracy calculation
- WebSocket `round_complete` event is fired immediately after insert

---

## 4. Table: `cluster_assignments`

**Class:** `ClusterAssignment`  
**Purpose:** Full history of every cluster reassignment event — tracks when factories moved between clusters  
**Rows:** Typically 4–8 (fires once per clustering event; may fire multiple times if plateau recurs)

```python
class ClusterAssignment(Base):
    __tablename__ = 'cluster_assignments'

    id               = Column(Integer, primary_key=True)
    round_num        = Column(Integer, nullable=False)      # round clustering fired on
    factory_id       = Column(Integer, ForeignKey('factories.factory_id'))
    cluster_id       = Column(Integer, nullable=False)      # assigned cluster (0 or 1)
    silhouette_score = Column(Float, nullable=True)         # quality of clustering split
    k_value          = Column(Integer, nullable=False)      # k=2 or k=3 (chosen by silhouette)
    reason           = Column(String(50), default='plateau_detected')
    timestamp        = Column(DateTime, default=datetime.utcnow)
```

**Sample rows after first clustering at round 10:**
```
round_num | factory_id | cluster_id | silhouette_score | k_value | reason
----------+------------+------------+------------------+---------+------------------
10        | 1          | 0          | 0.412            | 2       | plateau_detected
10        | 2          | 1          | 0.412            | 2       | plateau_detected
10        | 3          | 0          | 0.412            | 2       | plateau_detected
10        | 4          | 1          | 0.412            | 2       | plateau_detected
```

**Used by:**
- `GET /cluster-history` → topology page event list
- `GET /clusters` → current cluster assignment (latest row per factory)
- WebSocket `cluster_assigned` event

---

## 5. Table: `model_weights`

**Class:** `ModelWeight`  
**Purpose:** Checkpoint registry — stores the **file path** of saved `.pt` weight files, NOT the binary weights themselves  
**Note:** Actual weight files are too large for DB storage (30–90 KB per model × rounds × clusters)

```python
class ModelWeight(Base):
    __tablename__ = 'model_weights'

    id           = Column(Integer, primary_key=True)
    round_num    = Column(Integer, nullable=False)
    cluster_id   = Column(Integer, nullable=True)       # NULL = global model
    algorithm    = Column(String(20), nullable=False)   # "FedAvg"
    weights_path = Column(String(200), nullable=False)  # "weights/global_r10.pt"
    accuracy     = Column(Float, nullable=False)        # accuracy at save time
    timestamp    = Column(DateTime, default=datetime.utcnow)
```

**Sample rows:**
```
round_num | cluster_id | algorithm | weights_path              | accuracy
----------+------------+-----------+---------------------------+---------
5         | NULL       | FedAvg    | weights/global_r5.pt      | 0.621
10        | NULL       | FedAvg    | weights/global_r10.pt     | 0.640
10        | 0          | FedAvg    | weights/cluster_0_r10.pt  | 0.721
10        | 1          | FedAvg    | weights/cluster_1_r10.pt  | 0.698
20        | 0          | FedAvg    | weights/cluster_0_r20.pt  | 0.834
20        | 1          | FedAvg    | weights/cluster_1_r20.pt  | 0.759
```

---

## 6. Table: `experiments`

**Class:** `Experiment`  
**Purpose:** One row per complete FL training run — supports comparing different hyperparameter configurations

```python
class Experiment(Base):
    __tablename__ = 'experiments'

    id                    = Column(Integer, primary_key=True)
    run_id                = Column(String(50), unique=True)    # "run_20260515_161004"
    strategy              = Column(String(20))                  # "FedAvg" | "FedProx"
    k_value               = Column(Integer)                     # 2 or 3
    alpha_mode            = Column(String(20))                  # "grid_search" | "fixed"
    dp_on                 = Column(Boolean, default=False)
    global_accuracy       = Column(Float, nullable=True)        # final round accuracy
    best_cluster_accuracy = Column(Float, nullable=True)        # best cluster's accuracy
    notes                 = Column(Text, nullable=True)
    timestamp             = Column(DateTime, default=datetime.utcnow)
```

---

## 7. Table: `round_summaries`

**Class:** `RoundSummary`  
**Purpose:** One row per FL round (not per factory) — stores the two accuracy metrics shown side-by-side on the dashboard

```python
class RoundSummary(Base):
    __tablename__ = 'round_summaries'

    id                 = Column(Integer, primary_key=True)
    round_num          = Column(Integer, unique=True, nullable=False)
    clustered_accuracy = Column(Float, nullable=True)   # from aggregate_fit()
    naive_global       = Column(Float, nullable=True)   # from aggregate_evaluate()
    n_clients          = Column(Integer, nullable=True)  # how many factories reported
    clustering_fired   = Column(Boolean, default=False)  # True for rounds 10+
    timestamp          = Column(DateTime, default=datetime.utcnow)
```

**Two accuracy metrics explained:**
| Column | Source | Meaning |
|--------|--------|---------|
| `clustered_accuracy` | `aggregate_fit()` | Weighted avg of each factory's local training accuracy. Measures how well models fit their local data. |
| `naive_global` | `aggregate_evaluate()` | Flower's built-in: the global averaged model tested on each client's local data. Measures global model quality. |

The gap between these two is the **clustering benefit**: `clustered_accuracy - naive_global` shows how much the cluster-personalized models outperform the naive global average.

---

## 8. Table Relationships Diagram

```
factories (4 rows)
    │ factory_id (PK)
    │
    ├──► training_rounds (80+ rows)
    │        round_num, factory_id (FK), accuracy, loss, algorithm, cluster_id
    │
    └──► cluster_assignments (4–16 rows)
             round_num, factory_id (FK), cluster_id, silhouette_score, k_value

model_weights (20–40 rows)
    round_num, cluster_id, weights_path, accuracy
    (no FK to factories — stores global + per-cluster checkpoint paths)

round_summaries (20 rows)
    round_num (unique), clustered_accuracy, naive_global, clustering_fired
    (one aggregate row per round, not per factory)

experiments (1 row per run)
    run_id (unique), strategy, k_value, alpha_mode, dp_on, global_accuracy
```

---

## 9. Table Creation Order

Tables are created in dependency order by SQLAlchemy's `create_all()`:

```
1. factories          (no FK dependencies)
2. training_rounds    (depends on factories.factory_id)
3. cluster_assignments (depends on factories.factory_id)
4. model_weights      (no FK dependencies)
5. experiments        (no FK dependencies)
6. round_summaries    (no FK dependencies)
```

**The `create_all()` call in `main.py` startup:**
```python
@app.on_event("startup")
async def startup_event():
    create_tables()        # creates all 6 tables if not exist
    seed_factories()       # inserts 4 factory rows if table is empty
```
