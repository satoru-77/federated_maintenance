# FedPredict — Build Guide & Technical Documentation

**Project:** Federated Maintenance System (FedPredict)  
**Stack:** PyTorch · Flower FL · FastAPI · Django · PostgreSQL · D3.js  
**Dataset:** NASA CMAPSS (FD001–FD004) — turbofan engine degradation  
**Total documents:** 44 files

> This folder contains the complete academic-grade build guide for the FedPredict system. Each document covers one component at the code level — architecture decisions, data flow, mathematical foundations, and implementation details.

---

## How to Read This Guide

**New to the project?** Start with `01` → `02` → `03`–`04` → `05`–`09` → `10`–`12` → `14`–`16` → `17`–`21`.  
**Debugging a specific component?** Jump directly to the relevant numbered doc.  
**Academic report?** The NB docs (NB01–NB09) contain the full experimental justification for every design decision.

---

## Section 1 — System Overview

| Doc | File | Description |
|-----|------|-------------|
| 01 | [01_System_Architecture_Overview.md](01_System_Architecture_Overview.md) | Full system architecture: 5 processes, port map, startup sequence, data flow |
| 02 | [02_Database_Schema_All_Tables.md](02_Database_Schema_All_Tables.md) | PostgreSQL schema: all 6 tables, FK relationships, dual accuracy columns |

---

## Section 1B — Machine Learning Notebooks (Experimental Basis)

| Doc | File | Description |
|-----|------|-------------|
| NB01 | [NB01_Notebook_FD001_EDA_Training.md](NB01_Notebook_FD001_EDA_Training.md) | FD001 EDA, sliding window generation, CNN1D training |
| NB02 | [NB02_Notebook_FD002_EDA_Training.md](NB02_Notebook_FD002_EDA_Training.md) | FD002 EDA — 6-condition multi-altitude analysis |
| NB03 | [NB03_Notebook_FD003_EDA_Training.md](NB03_Notebook_FD003_EDA_Training.md) | FD003 EDA — 2-fault degradation modes |
| NB04 | [NB04_Notebook_FD004_EDA_Training.md](NB04_Notebook_FD004_EDA_Training.md) | FD004 EDA — combined multi-condition + 2-fault |
| NB05 | [NB05_Notebook_Dataset_Comparison.md](NB05_Notebook_Dataset_Comparison.md) | Cross-dataset comparison: engine count, sensor overlap, RUL distribution |
| NB06 | [NB06_Notebook_NonIID_Analysis.md](NB06_Notebook_NonIID_Analysis.md) | Non-IID proof via KL Divergence & KDE — justifies adaptive clustering |
| NB07 | [NB07_Notebook_Model_Comparison.md](NB07_Notebook_Model_Comparison.md) | CNN1D vs LSTM — 7,714 params wins on bandwidth & accuracy |
| NB08 | [NB08_Notebook_Centralized_vs_FL.md](NB08_Notebook_Centralized_vs_FL.md) | FL vs centralized: 13% privacy tax, clustering recovery |
| NB09 | [NB09_Notebook_SHAP_Analysis.md](NB09_Notebook_SHAP_Analysis.md) | Gradient saliency algorithm, sensor attribution, notebook↔production parity |

---

## Section 2 — Production ML Components

| Doc | File | Description |
|-----|------|-------------|
| 03 | [03_ML_CMAPSS_Dataset_Preprocessing.md](03_ML_CMAPSS_Dataset_Preprocessing.md) | `data_loader.py`: fixed 14-sensor strategy, 100-engine cap, scaler persistence |
| 04 | [04_ML_CNN1D_Architecture_Training.md](04_ML_CNN1D_Architecture_Training.md) | `model.py`: `AdaptiveAvgPool1d`, 7,714-param layer breakdown, FL bandwidth cost |

---

## Section 3 — Federated Learning Engine

| Doc | File | Description |
|-----|------|-------------|
| 05 | [05_FL_Server_FedAvg_Strategy.md](05_FL_Server_FedAvg_Strategy.md) | `server.py`: `aggregate_fit()` walkthrough, Byzantine exclusion, plateau detection, cluster model update |
| 06 | [06_FL_Client_Factory_Training.md](06_FL_Client_Factory_Training.md) | `client.py`: `fit()` training loop, DP noise, Byzantine flag injection, threshold=0.4 |
| 07 | [07_FL_Clustering_Algorithm_KMeans.md](07_FL_Clustering_Algorithm_KMeans.md) | `clustering.py`: weight gradient K-means, L2 normalization, silhouette selection |
| 08 | [08_FL_Personalization_AlphaBlending.md](08_FL_Personalization_AlphaBlending.md) | `personalization.py`: α grid search, blend formula, per-factory alpha rationale |
| 09 | [09_FL_Security_DP_Byzantine.md](09_FL_Security_DP_Byzantine.md) | `security.py`: Gaussian mechanism (σ formula), cosine similarity detection, attack example |

---

## Section 4 — Backend API (FastAPI)

| Doc | File | Description |
|-----|------|-------------|
| 10 | [10_Backend_FastAPI_App_Setup.md](10_Backend_FastAPI_App_Setup.md) | `main.py` setup: CORS, `ConnectionManager`, WebSocket endpoint, cross-process broadcast |
| 11 | [11_Backend_All_REST_Endpoints.md](11_Backend_All_REST_Endpoints.md) | All 19 REST routes with full code, request/response examples, Django callers |
| 12 | [12_Backend_WebSocket_Broadcasting.md](12_Backend_WebSocket_Broadcasting.md) | `db_logger.py`: DB writes + WS broadcast, upsert pattern, all 5 event types |

---

## Section 5 — SHAP Explainability API

| Doc | File | Description |
|-----|------|-------------|
| 14 | [14_SHAP_API_Startup_Model_Loading.md](14_SHAP_API_Startup_Model_Loading.md) | `shap_api.py` startup: `FACTORY_CONFIG`, per-factory sensor lists, model loading |
| 15 | [15_SHAP_API_Explain_Endpoint_Full.md](15_SHAP_API_Explain_Endpoint_Full.md) | `POST /explain`: schemas, forward pass, scenario overrides, gradient saliency math |
| 16 | [16_SHAP_API_Demo_Random_Engine.md](16_SHAP_API_Demo_Random_Engine.md) | `POST /explain/demo`: real test data engine selection, RUL lookup, synthetic seeds |

---

## Section 6 — Frontend Base

| Doc | File | Description |
|-----|------|-------------|
| 17 | [17_Frontend_Base_Layout_Design_System.md](17_Frontend_Base_Layout_Design_System.md) | `base.html`: design tokens, dot-grid texture, 3-font system, nav, live-dot, page loader |
| 18 | [18_Frontend_URL_Routing_ApiClient.md](18_Frontend_URL_Routing_ApiClient.md) | `urls.py` + `api_client.py`: two-level routing, None-safe HTTP wrapper, auth flow |

---

## Section 7 — Overview Page (Training Dashboard)

| Doc | File | Description |
|-----|------|-------------|
| 19 | [19_Frontend_Django_Views.md](19_Frontend_Django_Views.md) | `views.py`: all 8 view functions — session scoping, SHAP cache, sparkline generation |
| 20 | [20_Frontend_Overview_Layout_StatCards.md](20_Frontend_Overview_Layout_StatCards.md) | `overview.html` Part 1: stat cards, cluster panel, D3 chart grid, element ID registry |
| 21 | [21_Frontend_Canvas_D3_WebSocket.md](21_Frontend_Canvas_D3_WebSocket.md) | `overview.html` Part 2: canvas bubble physics, D3 dual-line chart, WS handlers |

---

## Section 8 — Explainability Page

| Doc | File | Description |
|-----|------|-------------|
| 24 | [24_Frontend_Explainability_ViewFunction.md](24_Frontend_Explainability_ViewFunction.md) | Explainability view: factory/scenario routing, SHAP call, sensor name map |
| 25 | [25_Frontend_Explainability_FactorySelector_Bar.md](25_Frontend_Explainability_FactorySelector_Bar.md) | Factory selector tabs + scenario button strip |
| 26 | [26_Frontend_Explainability_EngineFleet_Cards.md](26_Frontend_Explainability_EngineFleet_Cards.md) | Engine fleet status cards — cluster badge, alpha value, dataset info |
| 27 | [27_Frontend_Explainability_Prediction_ResultPanel.md](27_Frontend_Explainability_Prediction_ResultPanel.md) | Prediction result panel: FAILURE/HEALTHY badge, confidence meter |
| 28 | [28_Frontend_Explainability_LiveDataVerification.md](28_Frontend_Explainability_LiveDataVerification.md) | Live data verification panel: raw sensor table, engine metadata, RUL ground truth |
| 29 | [29_Frontend_Explainability_SHAP_WaterfallChart.md](29_Frontend_Explainability_SHAP_WaterfallChart.md) | SHAP waterfall chart: bar width scaling, red/blue direction coding |
| 30 | [30_Frontend_Explainability_AI_Explanation_Panel.md](30_Frontend_Explainability_AI_Explanation_Panel.md) | AI explanation panel + top-3 sensor sparklines |

---

## Section 9 — Other Dashboard Pages

| Doc | File | Description |
|-----|------|-------------|
| 31 | [31_Frontend_Simulation_Control_Panel.md](31_Frontend_Simulation_Control_Panel.md) | Simulation page: Start/Stop FL, speed slider, Byzantine inject button |
| 32 | [32_Frontend_Factories_List_Detail_Pages.md](32_Frontend_Factories_List_Detail_Pages.md) | Factories list + factory detail page with per-factory accuracy chart |
| 33 | [33_Frontend_Rounds_Log_Page.md](33_Frontend_Rounds_Log_Page.md) | Rounds log: filterable table, CSV export, accuracy color coding |
| 34 | [34_Frontend_Topology_Monitor_Pages.md](34_Frontend_Topology_Monitor_Pages.md) | Topology D3 force graph + live monitor polling page |

---

## Section 10 — Deployment

| Doc | File | Description |
|-----|------|-------------|
| 35 | [35_Deployment_Scripts_Docker_Setup.md](35_Deployment_Scripts_Docker_Setup.md) | `start_all.ps1`, `Dockerfile`, `docker-compose.yml`, environment variables |

---

## Quick Reference: Key Design Decisions

| Decision | Rationale | Doc |
|----------|-----------|-----|
| Fixed 14 sensors for FL | Weight tensor shape must match across factories for FedAvg | 03, 06 |
| CNN1D over LSTM | 7,714 params vs 50k+ → 86% less FL bandwidth | NB07, 04 |
| `AdaptiveAvgPool1d(1)` | Input-length-agnostic → same model handles seq_length 20–50 | 04 |
| 100-engine cap for FD002/FD004 | RAM management — 260/248 engines × float32 arrays → OOM risk | 03 |
| Threshold 0.4 not 0.5 | Safety-critical: missed failure worse than false alarm | 06, 15 |
| L2-normalize gradients for K-means | Clusters by update *direction*, not magnitude — avoids data-size bias | 07 |
| Median not mean for Byzantine detection | Median unaffected by extreme outliers (corrupted weights × 500) | 09 |
| Session-start scoping in `/metrics` | Prevents stale data from previous runs polluting live stat cards | 11, 19 |
| SHAP cache for static scenarios | healthy/degraded/critical windows are fixed-seed — never change | 19 |
| Cross-process HTTP for WS broadcast | FL server & FastAPI are separate processes — no shared memory | 10, 12 |

---

## Port Reference

| Port | Service | Command |
|------|---------|---------|
| 8000 | FastAPI REST + WebSocket | `uvicorn backend.main:app --port 8000` |
| 8001 | SHAP Explainability API | `uvicorn shap_api:app --port 8001` |
| 8002 | Django Dashboard | `python manage.py runserver 8002` |
| 8080 | Flower gRPC Server | `python -m server.server --rounds 20` |
| 5432 | PostgreSQL | `fl_maintenance2` database |
