# 01 — System Architecture Overview

**Project:** Federated Predictive Maintenance System  
**Dataset:** NASA CMAPSS (Commercial Modular Aero-Propulsion System Simulation)  
**Stack:** PyTorch · Flower · FastAPI · PostgreSQL · Django · SHAP

---

## 1. The Core Problem

Traditional predictive maintenance requires a central server to collect all sensor data from all factories. This creates two problems:
1. **Privacy risk** — raw engine sensor readings are proprietary industrial data. Competitors and attackers cannot see them.
2. **Data silos** — each factory has a different operating environment (climate, fuel, load), so a single centralized model trains on heterogeneous data and generalizes poorly.

**Federated Learning solves both:** each factory trains a local model on its own data, then only sends the model *weights* (not the data) to a central server. The server aggregates the weights into a global model. No raw data ever leaves the factory.

---

## 2. System Components

The system has 5 distinct layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER (Dashboard)                       │
│           Django app on port 8002 — HTML/CSS/JS/D3.js           │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP requests + WebSocket
┌───────────────────────────▼─────────────────────────────────────┐
│                     FASTAPI BACKEND (port 8000)                  │
│          REST endpoints + WebSocket broadcaster + DB ORM         │
└──────────────┬────────────────────────────┬─────────────────────┘
               │ SQLAlchemy                  │ Internal callback
┌──────────────▼──────────┐     ┌───────────▼─────────────────────┐
│  PostgreSQL (port 5432)  │     │    FLOWER FL SERVER (port 8080)  │
│  5 tables: rounds,       │     │    FedAvg aggregation           │
│  factories, clusters,    │     │    Byzantine detection          │
│  cluster_history,        │     │    Adaptive clustering          │
│  events                  │     │    Personalization              │
└─────────────────────────┘     └────────────┬────────────────────┘
                                              │ gRPC (Flower protocol)
            ┌───────────────────────────┬─────┴──────┬─────────────┐
            ▼                           ▼            ▼             ▼
   Factory 1 Client           Factory 2         Factory 3     Factory 4
   Mumbai · FD001             Berlin · FD002    Detroit·FD003 Tokyo·FD004
   100 engines                260 engines       100 engines   248 engines
   [CNN1D model]              [CNN1D model]     [CNN1D model] [CNN1D model]
   train locally              train locally     train locally train locally

                   ┌──────────────────────────────┐
                   │  SHAP API (port 8001)         │
                   │  Standalone Uvicorn service   │
                   │  Gradient saliency inference  │
                   │  Serves /explain endpoint     │
                   └──────────────────────────────┘
                   (called by Django and monitor_api)
```

---

## 3. The 4 Factories & Their Datasets

| Factory | Location | Dataset | Training engines | Test engines | Conditions |
|---------|----------|---------|-----------------|-------------|------------|
| Factory 1 | Mumbai | FD001 | 100 | 100 | 1 op condition, 1 fault mode |
| Factory 2 | Berlin | FD002 | 260 | 259 | 6 op conditions, 1 fault mode |
| Factory 3 | Detroit | FD003 | 100 | 100 | 1 op condition, 2 fault modes |
| Factory 4 | Tokyo | FD004 | 248 | 248 | 6 op conditions, 2 fault modes |

**Why different engine counts?** The NASA CMAPSS dataset has 4 sub-datasets (FD001–FD004) designed to test model robustness across increasing complexity. Factories with more operating conditions (FD002, FD004) have more data.

**Fault modes:** FD001 and FD002 only have a single failure type (HPC degradation). FD003 and FD004 include both HPC degradation and fan degradation — making Detroit and Tokyo harder classification problems.

---

## 4. Complete Data Flow (Training)

```
ROUND START
│
├── Flower server sends global model weights → each factory client
│
├── Each factory:
│     loads own CSV (train_FD00X.txt)
│     creates 30-cycle sliding windows
│     labels: FAILURE if RUL ≤ 30 cycles (binary classification)
│     trains CNN1D for 10 local epochs
│     applies Differential Privacy noise (ε=1.0)
│     sends updated weights back to server
│
├── Server receives 4 weight updates
│     runs Byzantine detector (cosine similarity to median)
│     excludes any factory with similarity < 0.5
│     FedAvg aggregation: weighted average by n_samples
│
├── After Round 10 (or on plateau):
│     Adaptive Clustering: K-means on normalized weight gradients
│     Tests k=2 and k=3, picks best silhouette score
│     Personalization: grid search α ∈ {0.1...0.9} per factory
│       final_weights = α × cluster_weights + (1-α) × local_weights
│
├── db_logger.py logs round result to PostgreSQL:
│     table: rounds (round_num, factory_id, accuracy, loss, algorithm, cluster_id, n_samples)
│
├── FastAPI broadcasts WebSocket event to all connected browsers:
│     {type: "round_complete", round_num, factory_id, accuracy}
│
└── ROUND END → next round begins
```

---

## 5. Complete Data Flow (Inference / Explainability)

```
User visits /explainability/?factory_id=1&scenario=random
│
├── Django views.py → POST http://localhost:8001/explain/demo
│     params: factory_id=1, scenario=random
│
├── SHAP API (shap_api.py):
│     loads Factory 1's trained CNN weights from fl_backend/weights/factory_1_model.pt
│     picks random engine from test_FD001.txt
│     selects last 30-cycle window
│     runs CNN forward pass → prediction (FAILURE/HEALTHY) + confidence
│     computes gradient saliency: x.requires_grad=True → backprop → x.grad
│     returns: prediction, confidence, shap_values (per sensor), top_sensors,
│              engine_id, actual_rul, actual_label, raw_sensor_sample
│
├── Django processes response:
│     confidence × 100 → percentage
│     builds template_shap_list (pct normalization)
│     builds template_top_list (top 3 sensors with labels)
│     builds raw_sensor_rows (unscaled values)
│
└── Renders explainability.html with all data
```

---

## 6. Directory Structure

```
Federated_Maintenance/
│
├── fl_backend/                    # ML + API backend
│   ├── server/
│   │   ├── server.py              # FLServer (Flower strategy), FedAvg, Byzantine detection
│   │   ├── clustering.py          # AdaptiveClustering (K-means on gradients)
│   │   ├── personalization.py     # PersonalizationManager (alpha grid search)
│   │   └── security.py            # DifferentialPrivacy + ByzantineDetector
│   │
│   ├── client/
│   │   ├── client.py              # FactoryClient (Flower NumPyClient)
│   │   ├── model.py               # CNN1D architecture
│   │   └── data_loader.py         # CMAPSS preprocessing + sliding windows
│   │
│   ├── backend/
│   │   ├── main.py                # FastAPI app, REST endpoints, WebSocket
│   │   ├── db.py                  # SQLAlchemy engine + session factory
│   │   ├── models.py              # ORM table definitions
│   │   └── db_logger.py           # FL round logging + WS broadcasting
│   │
│   ├── config.yaml                # All tunable parameters
│   ├── .env                       # DB credentials (not in git)
│   ├── start_fl.ps1               # Launch script for FL training
│   └── requirements.txt           # Python dependencies
│
├── fl_shap_dashboard/             # Django frontend
│   ├── core/
│   │   ├── settings.py            # Django settings
│   │   └── urls.py                # Global URL router
│   ├── dashboard/
│   │   ├── views.py               # All page view functions
│   │   ├── urls.py                # Dashboard URL patterns
│   │   └── api_client.py          # HTTP client to FastAPI backend
│   ├── templates/
│   │   ├── base.html              # Design system + nav + CSS tokens
│   │   └── pages/
│   │       ├── overview.html      # Training dashboard (D3.js + Canvas + WS)
│   │       ├── explainability.html # SHAP explainability page
│   │       ├── simulation.html    # Control panel + event log
│   │       ├── factories.html     # Factory card grid
│   │       ├── factory_detail.html # Per-factory chart + rounds table
│   │       ├── rounds.html        # Full training log + CSV export
│   │       ├── topology.html      # Cluster graph (standalone, own CSS)
│   │       └── monitor.html       # Live inference monitor (polling)
│   └── requirements.txt
│
├── machine_learning/
│   ├── notebooks/
│   │   └── shap_api.py            # Standalone SHAP/saliency API (Uvicorn port 8001)
│   ├── data/                      # NASA CMAPSS CSV files
│   └── venv/                      # Isolated ML virtualenv
│
├── start_all.ps1                  # Master launch script (3 services)
├── docker-compose.yml             # Container orchestration
├── MakeDocumentPlan.md            # Documentation master plan (this project)
└── old_summaries/                 # Old summary docs (deprecated)
```

---

## 7. Technology Stack Summary

| Layer | Technology | Why |
|-------|-----------|-----|
| ML Model | PyTorch CNN1D | 1D convolutions ideal for time-series sensor windows |
| FL Framework | Flower (flwr) | Clean NumPyClient API, handles gRPC transport |
| FL Algorithm | FedAvg | Weighted average by n_samples — handles unequal factory sizes |
| Privacy | Custom DP (Gaussian noise) | ε=1.0 budget — mathematically prevents data reconstruction |
| Security | Cosine similarity Byzantine detector | Robust against corrupted weight vectors |
| Clustering | Scikit-learn KMeans + silhouette | Groups factories by gradient direction similarity |
| Backend API | FastAPI + Uvicorn | Async, WebSocket support, auto OpenAPI docs |
| Database | PostgreSQL + SQLAlchemy | Relational DB for structured round/factory/cluster data |
| Frontend | Django 4 + Vanilla CSS | Template rendering, no JS framework needed |
| Charts | D3.js (overview) + Chart.js (detail) | D3 for real-time, Chart.js for simpler historical |
| Canvas animation | HTML5 Canvas API | Cluster bubble physics animation |
| Explainability | Gradient saliency (custom) | Lightweight alternative to full SHAP for time-series |
| Live updates | WebSocket (FastAPI → browser) | Push training events without polling |

---

## 8. Inter-Service Communication Map

```
Django (8002) ←──HTTP──► FastAPI (8000)
                              │
                              ├── GET /factories      → factory list
                              ├── GET /metrics        → summary stats
                              ├── GET /rounds         → training history
                              ├── GET /clusters       → cluster assignments
                              ├── GET /cluster-history→ cluster change log
                              ├── POST /sim/start     → trigger FL script
                              ├── POST /sim/stop      → kill FL processes
                              ├── POST /sim/inject    → inject scenario
                              └── WS /ws              → live event stream

Django (8002) ←──HTTP──► SHAP API (8001)
                              │
                              ├── POST /explain       → custom sensor window
                              └── POST /explain/demo  → random real engine

FastAPI (8000) ←──callback──► Flower Server (8080)
                              │
                              └── db_logger.py logs each round result
                                  + broadcasts to WebSocket clients

Flower Server ←──gRPC──► Factory Clients (1–4)
                              weights ↑↓ (bidirectional per round)
```
