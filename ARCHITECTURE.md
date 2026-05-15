# System Architecture — Federated Predictive Maintenance

**Project:** Federated Learning for Industrial Engine Failure Prediction  
**Dataset:** NASA CMAPSS (FD001–FD004)  
**Author:** Member 1 — Indrajit Das (202422027)

---

## Overview

This system applies **Federated Learning (FL)** to predict engine failures across 4 geographically
distributed factories — without any factory ever sharing raw sensor data. Each factory trains a local
CNN model on its own data, sends only model weights to the central Flower server, and the server
aggregates them into a global model that benefits everyone.

```
┌──────────────────────────────────────────────────────────────────┐
│                     SYSTEM OVERVIEW                              │
│                                                                  │
│   Factory 1         Factory 2         Factory 3       Factory 4  │
│  (Mumbai/FD001)   (Berlin/FD002)   (Detroit/FD003)  (Tokyo/FD004)│
│   100 engines       260 engines      100 engines     248 engines  │
│       │                 │                │               │        │
│   [CNN Model]       [CNN Model]      [CNN Model]    [CNN Model]  │
│   train locally     train locally    train locally  train locally │
│       │                 │                │               │        │
│   weights only ────────────────────────────────── weights only   │
│                              │                                    │
│                     ┌────────────────┐                           │
│                     │  Flower Server │  ←── aggregates weights   │
│                     │   (FedAvg /    │       (never raw data)     │
│                     │   FedProx)     │                           │
│                     └───────┬────────┘                           │
│                             │ logs results                       │
│                     ┌───────▼────────┐                           │
│                     │  PostgreSQL DB │                           │
│                     │  (5 tables)    │                           │
│                     └───────┬────────┘                           │
│                             │ serves data                        │
│                     ┌───────▼────────┐                           │
│                     │  FastAPI       │  ←── REST + WebSocket     │
│                     │  (port 8000)   │                           │
│                     └───────┬────────┘                           │
│                             │ calls API                          │
│                     ┌───────▼────────┐                           │
│                     │  Django        │                           │
│                     │  Dashboard     │  ←── Member 3's UI        │
│                     │  (port 8080)   │                           │
│                     └────────────────┘                           │
└──────────────────────────────────────────────────────────────────┘
```

---

## Port Map

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| Flower Server | 8080 | gRPC | FL training coordination |
| FastAPI Backend | 8000 | HTTP + WebSocket | REST API & live updates |
| PostgreSQL | 5432 | TCP | Persistent data storage |
| Django Dashboard | 8001 | HTTP | Web visualization |

---

## Data Flow

```
Step 1: SENSOR DATA (stays at factory — never leaves)
  train_FD001.txt ──► Factory 1 Client
  train_FD002.txt ──► Factory 2 Client
  train_FD003.txt ──► Factory 3 Client
  train_FD004.txt ──► Factory 4 Client

Step 2: LOCAL TRAINING
  Each client:
    loads data  ──► create sliding windows (30 timesteps × 14 sensors)
                ──► train CNN for local_epochs (default: 3)
                ──► compute updated weights

Step 3: WEIGHT TRANSFER (only weights, no raw data)
  Factory Client ──[weights + n_samples]──► Flower Server
  (repeats for all 4 factories per round)

Step 4: AGGREGATION (Flower Server)
  FedAvg: new_global = Σ(n_i × w_i) / Σ(n_i)
  Weighted so FD002 (260 engines) > FD001 (100 engines)

Step 5: CLUSTERING (after plateau detected, round ~10)
  Flower Server computes gradients per factory:
    gradient_i = global_weights - factory_weights
  K-Means on gradient matrix (4 factories × n_params)
  → Cluster A: {FD001, FD003} (single operating condition)
  → Cluster B: {FD002, FD004} (6 operating conditions)
  Each cluster runs its own FedAvg from round 11 onwards

Step 6: PERSONALIZATION (after clustering stabilises)
  blended_model = α × cluster_model + (1-α) × local_model
  Grid search α ∈ [0.1, 0.9] per factory
  Best α stored in DB → exposed via API

Step 7: LOGGING (after every round)
  Flower Server ──► PostgreSQL (training_rounds table)
  Flower Server ──► POST /ws/broadcast ──► Dashboard (live)

Step 8: DASHBOARD
  Django ──► GET /factories, /rounds, /clusters ──► FastAPI
  FastAPI ──► query PostgreSQL ──► return JSON
  WebSocket: ws://localhost:8000/ws ──► real-time updates
```

---

## Component Architecture

### 1. Factory Clients (`fl_backend/client/`)

Each of the 4 factory clients is an independent Python process:

```
python client.py --factory-id 1 --dataset FD001
python client.py --factory-id 2 --dataset FD002
python client.py --factory-id 3 --dataset FD003
python client.py --factory-id 4 --dataset FD004
```

**Client responsibilities:**
- Loads its own CMAPSS dataset (raw text files never leave the process)
- Implements `flwr.client.NumPyClient` interface:
  - `get_parameters()` → returns current model weights
  - `fit()` → trains locally for N epochs, returns updated weights + n_samples
  - `evaluate()` → validates on local test split, returns loss + accuracy
- Applies **Differential Privacy**: Gaussian noise added to weights before sending
- Uses CNN1D architecture (same model across all factories)

### 2. Flower Server (`fl_backend/server/server.py`)

Central coordinator — never sees raw sensor data.

**Server responsibilities:**
- Waits for all 4 clients to connect before starting
- Runs N rounds (default: 20, configurable in `config.yaml`)
- Each round:
  1. Sends current global weights to all clients
  2. Clients train locally and return updated weights
  3. Server performs **FedAvg** (or FedProx) aggregation
  4. Logs round results to PostgreSQL via `db_logger.py`
  5. Broadcasts round event via WebSocket
- **Plateau detection**: if accuracy improvement < `plateau_delta` for `plateau_patience` rounds → triggers clustering
- After clustering: each cluster runs its own separate FedAvg

### 3. Clustering Module (`fl_backend/server/clustering.py`)

Adaptive clustering based on gradient similarity:

```
After round R:
  For each factory i:
    gradient_i = flatten(global_weights) - flatten(factory_weights_i)
    gradient_i = gradient_i / ||gradient_i||   (normalize)

  Matrix G = stack([gradient_1, gradient_2, gradient_3, gradient_4])
  G.shape = (4, n_parameters)

  For k in [2, 3]:
    kmeans = KMeans(n_clusters=k).fit(G)
    score  = silhouette_score(G, kmeans.labels_)

  Select k with highest silhouette score
  Log assignments to cluster_assignments table
  Switch to cluster-specific FedAvg
```

### 4. Personalization Module (`fl_backend/server/personalization.py`)

Alpha blending after clustering stabilises:

```
For each factory i:
  For α in [0.1, 0.2, ..., 0.9]:
    blended = α × cluster_model_weights + (1-α) × local_model_weights_i
    load blended weights into CNN
    evaluate on factory i's validation set
    record AUC-ROC

  best_alpha = α that gave highest AUC-ROC
  UPDATE factories SET alpha_value = best_alpha WHERE factory_id = i
```

### 5. Security Module (`fl_backend/server/security.py`)

**Differential Privacy:**
```
sigma = sensitivity × sqrt(2 × ln(1.25 / delta)) / epsilon
noise = Normal(0, sigma²)
weights_noisy = weights + noise
```
Epsilon (ε) and delta (δ) configured in `config.yaml`.

**Byzantine Fault Detection:**
```
For each factory i:
  similarity_i = cosine_similarity(weights_i, median(all_weights))
  if similarity_i < byzantine_threshold:
    flag factory i as suspicious
    exclude from aggregation this round
    log to DB
```

### 6. FastAPI Backend (`fl_backend/backend/main.py`)

REST API consumed by the Django dashboard. All 12 endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/factories` | All factories + current status |
| GET | `/factories/{id}` | Single factory + last 20 rounds |
| POST | `/factories/register` | Auto-onboarding new factory |
| GET | `/factories/{id}/alpha` | Best personalization alpha |
| GET | `/factories/{id}/privacy` | Privacy budget status |
| GET | `/rounds` | All training rounds (filter by factory) |
| GET | `/clusters` | Current cluster assignments |
| GET | `/clusters/history` | Full cluster change history |
| GET | `/experiments` | All experiment runs |
| GET | `/metrics` | Prometheus-compatible metrics |
| POST | `/sim/speed` | Set round speed (slow/normal/fast) |
| POST | `/sim/inject` | Inject demo scenario |
| WS | `/ws` | WebSocket for live dashboard |
| POST | `/ws/broadcast` | Internal: FL server → dashboard |

### 7. PostgreSQL Database — 5 Tables

```
┌──────────────┐         ┌──────────────────┐
│  factories   │──────── │  training_rounds │
│──────────────│  1:many │──────────────────│
│ id (PK)      │         │ id (PK)          │
│ factory_id   │         │ round_num        │
│ name         │         │ factory_id (FK)  │
│ dataset      │         │ algorithm        │
│ n_engines    │         │ accuracy         │
│ cluster_id   │         │ loss             │
│ alpha_value  │         │ n_samples        │
│ status       │         │ cluster_id       │
│ created_at   │         │ timestamp        │
└──────────────┘         └──────────────────┘
       │
       │         ┌────────────────────┐
       └──────── │ cluster_assignments│
         1:many  │────────────────────│
                 │ id (PK)            │
                 │ round_num          │
                 │ factory_id (FK)    │
                 │ cluster_id         │
                 │ silhouette_score   │
                 │ k_value            │
                 │ reason             │
                 │ timestamp          │
                 └────────────────────┘

┌────────────────┐         ┌──────────────────┐
│  model_weights │         │   experiments    │
│────────────────│         │──────────────────│
│ id (PK)        │         │ id (PK)          │
│ round_num      │         │ run_id (UNIQUE)   │
│ cluster_id     │         │ strategy         │
│ algorithm      │         │ k_value          │
│ weights_path   │         │ alpha_mode       │
│ accuracy       │         │ dp_on            │
│ timestamp      │         │ global_accuracy  │
└────────────────┘         │ best_cluster_acc │
                           │ notes            │
                           │ timestamp        │
                           └──────────────────┘
```

### 8. Django Dashboard (`fl_shap_dashboard/`)

Member 3's responsibility — visualization layer only.  
Calls FastAPI via `api_client.py`. No direct DB access.

---

## Configuration (`fl_backend/config.yaml`)

All tunable parameters in one place — no magic numbers in code:

```yaml
fl:
  rounds: 20               # total FL training rounds
  min_clients: 4           # wait for all 4 factories
  local_epochs: 3          # epochs per factory per round
  plateau_patience: 5      # rounds without improvement → cluster
  plateau_delta: 0.001     # min improvement threshold

clustering:
  k_values: [2, 3]         # k values to try for K-Means
  default_k: 2             # fallback if silhouette scores tie

personalization:
  alpha_min: 0.1
  alpha_max: 0.9
  alpha_step: 0.1          # grid search granularity

security:
  dp_epsilon: 1.0          # privacy budget per round
  dp_delta: 0.00001        # failure probability
  byzantine_threshold: 0.5 # cosine similarity below this = suspicious

simulation:
  speed_slow: 60           # seconds between rounds (slow mode)
  speed_normal: 30         # seconds between rounds (normal mode)
  speed_fast: 10           # seconds between rounds (fast mode)
```

---

## Docker Deployment

Single command starts the entire system:

```bash
docker-compose up
```

```
┌─────────────────────────────────────────────────────┐
│                docker-compose.yml                   │
│                                                     │
│  postgres       ← database (port 5432)              │
│  fastapi        ← uvicorn main:app (port 8000)      │
│  flower_server  ← python server.py (port 8080)      │
│  client_1       ← python client.py --factory-id 1   │
│  client_2       ← python client.py --factory-id 2   │
│  client_3       ← python client.py --factory-id 3   │
│  client_4       ← python client.py --factory-id 4   │
│  dashboard      ← Django (port 8001)                │
└─────────────────────────────────────────────────────┘

Startup order:
  postgres (healthcheck) 
    └─► fastapi (depends_on postgres)
          └─► flower_server (depends_on fastapi)
                └─► client_1, client_2, client_3, client_4
```

Environment variables via `.env`:
```
DB_HOST=postgres
DB_PORT=5432
DB_NAME=fl_maintenance
DB_USER=fl_user
DB_PASSWORD=yourpassword
FL_ROUNDS=20
DP_EPSILON=1.0
```

---

## FL Algorithm Details

### FedAvg (Federated Averaging)

```
Round r:
  Server broadcasts global weights W_r to all clients
  
  Each factory i trains locally:
    W_i = local_train(W_r, factory_data_i, epochs=3)
  
  Server aggregates:
    W_{r+1} = Σ(n_i × W_i) / Σ(n_i)
  
  where n_i = number of training windows for factory i
  (FD002 contributes more due to larger dataset)
```

### FedProx (Proximal Term Variant)

Adds a proximal term to local training loss to prevent client drift:

```
local_loss_i = original_loss + (μ/2) × ||W_i - W_global||²
```

Especially beneficial for Non-IID data (FD002/FD004 have 6 operating 
conditions vs FD001/FD003 with 1 — causing significant weight drift).

### Cluster-specific FedAvg (after round ~10)

```
Cluster A {Factory 1, Factory 3}:
  W_A_{r+1} = (n_1×W_1 + n_3×W_3) / (n_1 + n_3)

Cluster B {Factory 2, Factory 4}:
  W_B_{r+1} = (n_2×W_2 + n_4×W_4) / (n_2 + n_4)

Each factory receives its cluster model, not the global model
```

---

## Model Architecture (CNN1D)

The same architecture is used across all factories and clusters:

```
Input: (batch_size, 30 timesteps, 14 sensors)
  │
  ├─ Permute → (batch_size, 14, 30)
  │
  ├─ Conv1D(14→32, kernel=3, padding=1) + ReLU
  │
  ├─ Conv1D(32→64, kernel=3, padding=1) + ReLU
  │
  ├─ AdaptiveAvgPool1d(1) → (batch_size, 64, 1)
  │
  ├─ Squeeze → (batch_size, 64)
  │
  ├─ Dropout(0.3)
  │
  └─ Linear(64 → 2)

Output: [P(healthy), P(failure)]
Label:  RUL ≤ 30 cycles → failure=1, else healthy=0
Total parameters: ~14,000  (small → fast weight transfer per FL round)
```

Why CNN1D for FL?
- **14k parameters** vs LSTM's 50k → 3.5× less data per weight transfer
- **Fastest local training** → critical when running 20 rounds × 4 factories
- **AUC-ROC ~0.96** on FD001 with acceptable miss rate

---

## Privacy Guarantee

```
What is NEVER shared between factories:
  ✗ Raw sensor readings (train_FD001.txt etc.)
  ✗ Engine IDs or cycle counts
  ✗ Failure labels
  ✗ Any derived feature vectors

What IS shared (from factory to server only):
  ✓ Model weights (14,000 floating point numbers)
  ✓ Number of training samples (n_samples)
  ✓ Accuracy / loss scalar (for logging)

Additional protection:
  ✓ Gaussian noise added to weights before transmission (DP)
  ✓ Byzantine detection excludes suspicious clients
  ✓ Server never stores or forwards raw gradients
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| CNN1D over LSTM | 3.5× fewer parameters = faster FL rounds |
| FedAvg weighted by n_samples | FD002 has 2.6× more data than FD001 — should have proportional influence |
| Plateau detection before clustering | Clustering too early hurts convergence; wait for global model to stabilise |
| K-Means on gradient vectors (not weights) | Gradients capture *direction of learning* — more meaningful than raw weight similarity |
| Silhouette score for k selection | Objective metric — avoids arbitrary k choice |
| Alpha grid search per factory | Optimal blend differs per factory due to Non-IID data |
| 5432/8000/8080/8001 ports | No conflicts; each service fully independent |
| `.env` for secrets | Credentials never hardcoded; easy to change without code edits |
