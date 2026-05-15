# 35 — Deployment Scripts, Docker & System Configuration

**Files covered:**
- `start_all.ps1` (root) — boots all three services
- `fl_backend/start_fl.ps1` — starts the Flower FL training loop
- `fl_backend/config.yaml` — all tunable FL parameters
- `fl_backend/.env` — database + port environment variables
- `fl_backend/Dockerfile` — Docker image for the backend
- `docker-compose.yml` (root) — container orchestration

---

## 1. System Architecture: Three Independent Services

The system is split across three separate processes that must ALL be running for the full dashboard to work:

| Service | Port | Process | Start command |
|---------|------|---------|--------------|
| FastAPI Backend | `8000` | Uvicorn | `uvicorn backend.main:app --port 8000` |
| SHAP Explainability API | `8001` | Uvicorn | `uvicorn shap_api:app --port 8001` |
| Django Dashboard | `8002` | Django dev server | `python manage.py runserver 8002` |

The **FL Training Loop** (Flower server + 4 factory clients) runs separately and connects to the FastAPI backend via an internal callback. It is NOT a web service — it's a set of Python processes that communicate via gRPC (Flower's protocol).

---

## 2. `start_all.ps1` — Master Launch Script

**Location:** `d:\PROJECTS\Federated_Maintenance\start_all.ps1`  
**Purpose:** Boots the three web services. Does NOT start FL training (that's separate).

```powershell
Write-Host "Starting the complete Federated Learning System..." -ForegroundColor Green

# ── Service 1: FastAPI Backend (Port 8000) ────────────────────────
$backendPath = Join-Path -Path $PWD -ChildPath "fl_backend"
Set-Location -Path $backendPath
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$backendPath'; venv\Scripts\activate; uvicorn backend.main:app --reload --port 8000"

# ── Service 2: SHAP Explainability API (Port 8001) ────────────────
$shapPath    = Join-Path -Path $PSScriptRoot -ChildPath "machine_learning\notebooks"
$shapVenvPath = Join-Path -Path $PSScriptRoot -ChildPath "machine_learning\venv\Scripts\activate.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$shapPath'; . '$shapVenvPath'; python shap_api.py"

# ── Service 3: Django Dashboard (Port 8002) ───────────────────────
$dashboardPath = Join-Path -Path $PSScriptRoot -ChildPath "fl_shap_dashboard"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$dashboardPath'; venv\Scripts\activate; python manage.py runserver 8002"

Write-Host "FL Backend API: http://localhost:8000/docs"
Write-Host "SHAP API:       http://localhost:8001/docs"
Write-Host "Dashboard:      http://localhost:8002"
Write-Host "Login: admin / admin123"
```

**Key design decisions:**
- `Start-Process powershell` opens each service in a **new PowerShell window** (not background)
- Each window runs `venv\Scripts\activate` before the service command — each service has its own isolated virtual environment
- The SHAP API uses a **different venv** (`machine_learning\venv`) than the backend (`fl_backend\venv`) and dashboard (`fl_shap_dashboard\venv`) — this isolates the heavy ML dependencies (PyTorch, SHAP) from the web frameworks
- `$PSScriptRoot` = the directory where the script is located (root of project)
- SHAP API uses `python shap_api.py` not `uvicorn shap_api:app` — `shap_api.py` calls `uvicorn.run()` internally at the bottom

---

## 3. `fl_backend/start_fl.ps1` — FL Training Launch Script

**Location:** `d:\PROJECTS\Federated_Maintenance\fl_backend\start_fl.ps1`  
**Purpose:** Starts the actual federated learning — Flower server + all 4 factory clients.  
**Run from:** `fl_backend/` directory after `start_all.ps1` has already started the backend.

```powershell
Write-Host "Starting FL Predictive Maintenance System..." -ForegroundColor Green

# ── Terminal 1: FastAPI Backend (must be running already) ──────────
# (Launches a new terminal for it if not already running)
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; uvicorn backend.main:app --reload --port 8000"

Start-Sleep -Seconds 5    # Wait for API to boot

# ── Terminal 2: Flower Server ─────────────────────────────────────
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; python -m server.server --rounds 20 --algorithm FedAvg"

Start-Sleep -Seconds 10   # Wait for server to be ready before clients connect

# ── Terminal 3: Factory 1 — Mumbai (FD001) ────────────────────────
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; python -m client.client --factory-id 1"

Start-Sleep -Seconds 1

# ── Terminal 4: Factory 2 — Berlin (FD002) ────────────────────────
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; python -m client.client --factory-id 2"

Start-Sleep -Seconds 1

# ── Terminal 5: Factory 3 — Detroit (FD003) ───────────────────────
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; python -m client.client --factory-id 3"

Start-Sleep -Seconds 1

# ── Terminal 6: Factory 4 — Tokyo (FD004) ────────────────────────
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; python -m client.client --factory-id 4"

Write-Host "FastAPI docs: http://localhost:8000/docs"
Write-Host "Rounds data:  http://localhost:8000/rounds"
```

**Startup sequence rationale:**
| Step | Wait | Why |
|------|------|-----|
| Start FastAPI | 5s | DB connection + route registration must complete before Flower server tries to log to it |
| Start Flower server | 10s | gRPC server must open and be listening before any client tries to connect |
| Start each client | 1s stagger | Prevents all 4 clients from hitting the server simultaneously during handshake |

**Module invocation syntax:**
```
python -m server.server   →  runs fl_backend/server/server.py as a module
python -m client.client   →  runs fl_backend/client/client.py as a module
```
The `-m` flag is required because these modules use relative imports (e.g. `from .model import CNN1D`).

---

## 4. `fl_backend/config.yaml` — Central Configuration

All tunable FL parameters in one file. Read by `server.py`, `client.py`, `clustering.py`, `personalization.py`, and `security.py` at startup.

```yaml
fl:
  rounds: 20              # Total FL communication rounds
  min_clients: 4          # Minimum factories that must connect before training starts
  local_epochs: 10        # Epochs each factory trains locally per round
  plateau_patience: 4     # Rounds of no improvement before triggering re-clustering
  plateau_delta: 0.02     # Minimum accuracy delta to count as "improvement"

clustering:
  k_values: [2, 3]        # K-means tries both k=2 and k=3, picks best silhouette score
  default_k: 2            # Fallback k if silhouette scoring fails

personalization:
  alpha_min: 0.1          # Minimum blending weight (10% global, 90% local)
  alpha_max: 0.9          # Maximum blending weight (90% global, 10% local)
  alpha_step: 0.1         # Grid search step → tries 0.1, 0.2, ..., 0.9

security:
  dp_epsilon: 1.0         # Differential privacy budget (lower = more noise = more private)
  dp_delta: 0.00001       # DP delta (probability of privacy failure)
  byzantine_threshold: 0.5  # Min cosine similarity to median; below = flagged as Byzantine

simulation:
  speed_slow: 60          # Simulated delay between rounds in slow mode (seconds)
  speed_normal: 30        # Normal mode delay
  speed_fast: 10          # Fast mode delay
```

**How config.yaml is read in Python (example from server.py):**
```python
import yaml
with open('config.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

ROUNDS           = cfg['fl']['rounds']            # 20
MIN_CLIENTS      = cfg['fl']['min_clients']        # 4
PLATEAU_PATIENCE = cfg['fl']['plateau_patience']   # 4
K_VALUES         = cfg['clustering']['k_values']   # [2, 3]
DP_EPSILON       = cfg['security']['dp_epsilon']   # 1.0
BYZ_THRESHOLD    = cfg['security']['byzantine_threshold']  # 0.5
```

---

## 5. `fl_backend/.env` — Environment Variables

**Never committed to git** (listed in `.gitignore`). Contains secrets and local configuration:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fl_maintenance2
DB_USER=postgres
DB_PASSWORD=indra10
FL_API_HOST=0.0.0.0
FL_API_PORT=8000
FLOWER_SERVER_HOST=0.0.0.0
FLOWER_SERVER_PORT=8080
```

**How `.env` is loaded in `backend/main.py` and `backend/db.py`:**
```python
from dotenv import load_dotenv
import os
load_dotenv()

DB_URL = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
# postgresql://postgres:indra10@localhost:5432/fl_maintenance2
```

**Database:** PostgreSQL. The database `fl_maintenance2` must exist before starting. Create it with:
```sql
CREATE DATABASE fl_maintenance2;
```
SQLAlchemy creates the tables automatically on first run via `Base.metadata.create_all(engine)`.

---

## 6. `fl_backend/Dockerfile` — Container Image

```dockerfile
FROM python:3.10-slim               # Minimal Python 3.10 base image

WORKDIR /app

# Install gcc (required for some native Python package builds)
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Install dependencies (separate file from requirements.txt — lighter, no ML libs)
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy all source files into the container
COPY . .

EXPOSE 8000

# Start FastAPI on all interfaces so Docker can forward the port
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Note:** `requirements-docker.txt` is a lighter version of `requirements.txt` that omits PyTorch, SHAP, and other heavy ML libraries — the Docker container only runs the API server, not the training loop.

---

## 7. `docker-compose.yml` — Container Orchestration

```yaml
services:

  backend:
    build:
      context: ./fl_backend       # Uses fl_backend/Dockerfile
      dockerfile: Dockerfile
    ports:
      - "8000:8000"               # host:container port mapping
    volumes:
      - ./fl_backend:/app         # live-reload: source changes reflected without rebuild

  dashboard:
    build:
      context: ./fl_shap_dashboard
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    depends_on:
      - backend                   # container starts only after backend is running
    volumes:
      - ./fl_shap_dashboard:/app
```

**Usage:**
```bash
# Build both images
docker-compose build

# Start both containers (detached)
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f dashboard

# Stop and remove containers
docker-compose down
```

**Limitation:** The Docker setup only containerises the Backend API and Dashboard. The FL training loop (Flower server + clients) must still be run manually since it requires GPU/CPU access and direct file system access to the CMAPSS dataset files.

---

## 8. Complete Startup Checklist

### Prerequisites
- [ ] PostgreSQL running with database `fl_maintenance2` created
- [ ] `fl_backend/venv` created with `pip install -r requirements.txt`
- [ ] `machine_learning/venv` created with `pip install -r requirements.txt`
- [ ] `fl_shap_dashboard/venv` created with `pip install -r requirements.txt`
- [ ] `fl_backend/.env` configured with correct DB credentials
- [ ] CMAPSS dataset files present in `machine_learning/data/`
- [ ] Trained model weights present in `fl_backend/weights/`

### Launch Order
```
Step 1:  Run start_all.ps1               → Opens 3 terminal windows
Step 2:  Wait ~10s for all services to boot
Step 3:  Open http://localhost:8002      → Login: admin / admin123
Step 4:  Run fl_backend/start_fl.ps1    → Opens 6 more terminal windows
Step 5:  Watch dashboard Overview page  → Training data streams in via WebSocket
```

### Port Summary
| Port | Service | URL |
|------|---------|-----|
| 5432 | PostgreSQL | (internal only) |
| 8000 | FastAPI Backend | http://localhost:8000/docs |
| 8001 | SHAP API | http://localhost:8001/docs |
| 8002 | Django Dashboard | http://localhost:8002 |
| 8080 | Flower gRPC server | (internal FL comms only) |
