fl_backend/
  backend/
    __init__.py        ← empty file
    main.py            ← FastAPI app
    models.py          ← SQLAlchemy database models
    db.py              ← database connection
    api_client.py      ← (empty for now)
  client/
    __init__.py        ← empty file
    client.py          ← Flower client (empty for now)
    model.py           ← COPY from machine_learning/notebooks/model.py
    data_loader.py     ← COPY from machine_learning/notebooks/data_loader.py
  server/
    __init__.py        ← empty file
    server.py          ← Flower server (empty for now)
    clustering.py      ← (empty for now)
  weights/             ← folder, leave empty
  logs/                ← folder, leave empty
  .env                 ← environment variables
  config.yaml          ← all settings
  requirements.txt     ← all dependencies
  docker-compose.yml   ← (empty for now)


  cd D:\PROJECTS\Federated_Maintenance\fl_backend
New-Item -ItemType Directory -Path backend, client, server, weights, logs
New-Item -ItemType File -Path backend\__init__.py
New-Item -ItemType File -Path client\__init__.py
New-Item -ItemType File -Path server\__init__.py

cd D:\PROJECTS\Federated_Maintenance\fl_backend
python -m venv venv
venv\Scripts\activate

create requirements.txt

fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
python-dotenv==1.0.0
pydantic==2.5.0
pyyaml==6.0.1
flwr==1.6.0
torch==2.1.0
numpy==1.26.2
scikit-learn==1.3.2
websockets==12.0

pip install -r requirements.txt

.\start_fl.ps1

STEP 7 — Run everything and verify
Open terminal in fl_backend/ with venv active.
Option A — Run the startup script (opens 6 terminals):
powershellcd D:\PROJECTS\Federated_Maintenance\fl_backend
venv\Scripts\activate
.\start_fl.ps1
Option B — Run manually (easier to see what's happening):
Terminal 1 — FastAPI:
powershellcd D:\PROJECTS\Federated_Maintenance\fl_backend
venv\Scripts\activate
uvicorn backend.main:app --reload --port 8000
Terminal 2 — Flower server:
powershellcd D:\PROJECTS\Federated_Maintenance\fl_backend
venv\Scripts\activate
python -m server.server --rounds 5 --algorithm FedAvg
Terminal 3 — Factory 1:
powershellcd D:\PROJECTS\Federated_Maintenance\fl_backend
venv\Scripts\activate
python -m client.client --factory-id 1
Terminal 4 — Factory 2:
powershellcd D:\PROJECTS\Federated_Maintenance\fl_backend
venv\Scripts\activate
python -m client.client --factory-id 2
Terminal 5 — Factory 3:
powershellcd D:\PROJECTS\Federated_Maintenance\fl_backend
venv\Scripts\activate
python -m client.client --factory-id 3
Terminal 6 — Factory 4:
powershellcd D:\PROJECTS\Federated_Maintenance\fl_backend
venv\Scripts\activate
python -m client.client --factory-id 4
Start them in this order:

FastAPI first
Flower server second (it waits for clients)
Then all 4 clients (start them quickly one after another)


WHAT YOU SHOULD SEE
Server terminal:
FL Server starting
Algorithm:  FedAvg
Rounds:     5
Min clients:4

[Server] === Round 1 — aggregating ===
  [DB] Round 1 | Factory 1 | Acc=0.7823 | Loss=0.4521 | logged ✓
  [DB] Round 1 | Factory 2 | Acc=0.7234 | Loss=0.5102 | logged ✓
  [DB] Round 1 | Factory 3 | Acc=0.7901 | Loss=0.4312 | logged ✓
  [DB] Round 1 | Factory 4 | Acc=0.7012 | Loss=0.5823 | logged ✓
[Server] Round 1 | Global accuracy: 0.7493 | Clients: 4
Each client terminal:
Factory 1 client starting
Connecting to server: localhost:8080
Loading data...
Factory 1: 14 useful sensors
Factory 1: 17731 windows created
Ready ✓
  [Factory 1] Trained 3 epochs | Loss=0.4521
  [Factory 1] Val accuracy=0.7823 | Loss=0.4312
After rounds complete — check the database:
http://localhost:8000/rounds
Should return a list of round results with real accuracy numbers.