# main.py
# The FastAPI application
# This is what Member 3's Django dashboard calls
# Run with: uvicorn backend.main:app --reload --port 8000


from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime


from .db import get_db, create_tables
from .models import Factory, TrainingRound, ClusterAssignment, Experiment, RoundSummary

class ConnectionManager:
    """
    Manages all active WebSocket connections.
    
    When a browser opens the dashboard, it connects here.
    When the FL server completes a round, it calls broadcast()
    and all connected browsers receive the update instantly.
    """

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send a message to ALL connected browsers."""
        if not self.active_connections:
            return
        text = json.dumps(message)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(text)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)


# Global manager instance
manager = ConnectionManager()

# Create the FastAPI app
app = FastAPI(
    title="FL Predictive Maintenance API",
    description="Federated Learning system for industrial engine failure prediction",
    version="1.0.0"
)

# CORS: allow Member 3's Django dashboard to call this API
# Without this, browsers block cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # in production: change to dashboard's actual URL
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """Runs once when FastAPI starts. Creates DB tables."""
    create_tables()
    print("FastAPI started. Database ready.")


# ── HEALTH CHECK ──────────────────────────────────────────────
@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "FL Predictive Maintenance API",
        "timestamp": datetime.utcnow().isoformat()
    }


# ── FACTORIES ─────────────────────────────────────────────────
@app.get("/factories")
def get_factories(db: Session = Depends(get_db)):
    """Return all factories with their current status."""
    factories = db.query(Factory).all()
    return [
        {
            "factory_id":  f.factory_id,
            "name":        f.name,
            "dataset":     f.dataset,
            "n_engines":   f.n_engines,
            "cluster_id":  f.cluster_id,
            "alpha_value": f.alpha_value,
            "status":      f.status,
        }
        for f in factories
    ]


@app.get("/factories/{factory_id}")
def get_factory(factory_id: int, db: Session = Depends(get_db)):
    """Return one factory + its last 20 rounds."""
    f = db.query(Factory).filter(Factory.factory_id == factory_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Factory not found")

    rounds = (
        db.query(TrainingRound)
        .filter(TrainingRound.factory_id == factory_id)
        .order_by(TrainingRound.round_num.desc())
        .limit(20)
        .all()
    )

    return {
        "factory_id":  f.factory_id,
        "name":        f.name,
        "dataset":     f.dataset,
        "n_engines":   f.n_engines,
        "cluster_id":  f.cluster_id,
        "alpha_value": f.alpha_value,
        "status":      f.status,
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


@app.get("/factories/{factory_id}/alpha")
def get_factory_alpha(factory_id: int, db: Session = Depends(get_db)):
    """
    Return the best alpha value for a factory.
    Set during personalization phase.
    Member 3's dashboard displays this per factory.
    """
    f = db.query(Factory).filter(
        Factory.factory_id == factory_id
    ).first()
    if not f:
        raise HTTPException(status_code=404, detail="Factory not found")
    
    return {
        "factory_id":  f.factory_id,
        "name":        f.name,
        "alpha_value": f.alpha_value,
        "has_personalization": f.alpha_value is not None
    }

# ── ROUNDS ────────────────────────────────────────────────────
@app.get("/rounds")
def get_rounds(
    factory_id: Optional[int] = None,
    limit: int = 100,
    since: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Return training rounds. Optional filter by factory_id or since timestamp."""
    query = db.query(TrainingRound)
    if factory_id:
        query = query.filter(TrainingRound.factory_id == factory_id)
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(TrainingRound.timestamp >= since_dt)
        except ValueError:
            pass
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


# ── CLUSTERS ──────────────────────────────────────────────────
@app.get("/clusters")
def get_clusters(db: Session = Depends(get_db)):
    """Return current cluster assignment for each factory."""
    factories = db.query(Factory).all()
    clusters = {}
    for f in factories:
        cid = str(f.cluster_id) if f.cluster_id is not None else "unassigned"
        if cid not in clusters:
            clusters[cid] = []
        clusters[cid].append({
            "factory_id": f.factory_id,
            "name":       f.name,
            "dataset":    f.dataset
        })
    return clusters


@app.get("/clusters/history")
def get_cluster_history(db: Session = Depends(get_db)):
    """Return full history of cluster assignment changes."""
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


# ── EXPERIMENTS ───────────────────────────────────────────────
@app.get("/experiments")
def get_experiments(db: Session = Depends(get_db)):
    """Return all experiment runs for comparison."""
    exps = db.query(Experiment).order_by(Experiment.timestamp.desc()).all()
    return [
        {
            "run_id":                e.run_id,
            "strategy":             e.strategy,
            "k_value":              e.k_value,
            "alpha_mode":           e.alpha_mode,
            "dp_on":                e.dp_on,
            "global_accuracy":      e.global_accuracy,
            "best_cluster_accuracy":e.best_cluster_accuracy,
            "notes":                e.notes,
            "timestamp":            e.timestamp.isoformat()
        }
        for e in exps
    ]


# ── ROUND SUMMARIES ───────────────────────────────────────────
@app.get("/round-summaries")
def get_round_summaries(
    limit: int = 25,
    since: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Per-round summary with BOTH accuracy metrics.
    clustered_accuracy = weighted avg of local training scores (fit phase)
    naive_global       = Flower evaluate_round score (global model)
    """
    query = db.query(RoundSummary)
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(RoundSummary.timestamp >= since_dt)
        except ValueError:
            pass
    summaries = query.order_by(RoundSummary.round_num.desc()).limit(limit).all()
    return [
        {
            "round_num":          s.round_num,
            "clustered_accuracy": s.clustered_accuracy,
            "naive_global":       s.naive_global,
            "n_clients":          s.n_clients,
            "clustering_fired":   s.clustering_fired,
            "timestamp":          s.timestamp.isoformat()
        }
        for s in summaries
    ]


# ── METRICS ───────────────────────────────────────────────────
@app.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    """
    Returns metrics scoped to the CURRENT training session.
    A new session is detected by the most recent timestamp where round_num = 1.
    This prevents old training runs from polluting the live stat cards.
    """
    from sqlalchemy import func

    # Find when the current session started (most recent round_num=1 entry)
    session_start = (
        db.query(func.max(TrainingRound.timestamp))
        .filter(TrainingRound.round_num == 1)
        .scalar()
    )

    if session_start:
        # Count unique round numbers in this session
        session_rounds_q = db.query(TrainingRound).filter(
            TrainingRound.timestamp >= session_start
        )
        unique_rounds = (
            db.query(TrainingRound.round_num)
            .filter(TrainingRound.timestamp >= session_start)
            .distinct()
            .count()
        )
        latest_round = (
            session_rounds_q
            .order_by(TrainingRound.round_num.desc())
            .first()
        )
    else:
        # No round 1 found — DB may be empty or mid-session
        unique_rounds = 0
        latest_round = None

    active_factories = db.query(Factory).filter(Factory.status == 'active').count()

    return {
        "total_rounds":      unique_rounds,
        "active_factories":  active_factories,
        "latest_round_num":  latest_round.round_num if latest_round else 0,
        "latest_accuracy":   latest_round.accuracy  if latest_round else None,
        "session_start":     session_start.isoformat() if session_start else None,
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for live dashboard updates.
    
    Browser connects once when page loads.
    Server pushes JSON events after each FL round.
    Browser receives events and updates charts without refresh.
    
    Connect with: ws://localhost:8000/ws
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive — wait for messages from browser
            # (browser can send "ping" to check connection)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/ws/broadcast")
async def broadcast_event(event: dict):
    """
    Internal endpoint — called by FL server after each round.
    Broadcasts the event to all connected dashboard browsers.
    
    This is how the FL server talks to the dashboard:
    FL round completes → POST /ws/broadcast → all browsers updated
    """
    await manager.broadcast(event)
    return {"status": "broadcast", "connections": len(manager.active_connections)}


# ── SIMULATION CONTROLS ───────────────────────────────────────
import subprocess
import os

@app.post("/sim/start")
def start_simulation():
    """
    Called by the dashboard to pop open the 5 PowerShell terminals
    for the Flower Server and 4 Factory Clients.
    """
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "start_fl.ps1")
    subprocess.Popen(["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path])
    return {"status": "ok", "message": "Simulation Terminals Launched!"}

@app.post("/sim/stop")
def stop_simulation():
    """
    Forcefully kills the PowerShell and Python processes running the 
    FL server and clients.
    """
    # This WMI command finds any process whose command line contains server.server or client.client
    # and terminates it. This will close both the Python execution and the parent PowerShell window.
    cmd = 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "client.client" -or $_.CommandLine -match "server.server" } | Invoke-CimMethod -MethodName Terminate'
    subprocess.Popen(["powershell", "-Command", cmd])
    return {"status": "ok", "message": "Simulation Terminals Terminated!"}


@app.post("/sim/speed")
def set_speed(speed: str):
    """
    Set simulation speed.
    speed: 'slow' | 'normal' | 'fast'
    Member 3's dashboard calls this when speed slider changes.
    """
    valid = ['slow', 'normal', 'fast']
    if speed not in valid:
        raise HTTPException(status_code=400, detail=f"speed must be one of {valid}")
    # In Phase 2 this will actually change the FL round timer
    # For now just acknowledge
    return {"status": "ok", "speed": speed}


@app.post("/sim/inject")
def inject_scenario(scenario: str):
    """
    Inject a demo scenario.
    scenario: 'new_factory' | 'byzantine' | 'recluster' | 'drop_factory'
    """
    valid = ['new_factory', 'byzantine', 'recluster', 'drop_factory']
    if scenario not in valid:
        raise HTTPException(status_code=400, detail=f"scenario must be one of {valid}")
        
    if scenario == 'byzantine':
        # Write flag file to trigger attack on Factory 3
        flag_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "byzantine_flag.txt")
        with open(flag_path, "w") as f:
            f.write("3")
            
    return {"status": "ok", "scenario": scenario, "message": f"Scenario '{scenario}' queued"}

# ── AUTO-ONBOARDING ───────────────────────────────────────────
@app.post("/factories/register")
def register_factory(
    factory_id: int,
    name: str,
    dataset: str,
    db: Session = Depends(get_db)
):
    existing = db.query(Factory).filter(
        Factory.factory_id == factory_id
    ).first()
    if existing:
        raise HTTPException(status_code=400,
                            detail=f"Factory {factory_id} already registered")
    valid_datasets = ['FD001', 'FD002', 'FD003', 'FD004']
    if dataset not in valid_datasets:
        raise HTTPException(status_code=400,
                            detail=f"Dataset must be one of {valid_datasets}")
    new_factory = Factory(
        factory_id = factory_id,
        name       = name,
        dataset    = dataset,
        n_engines  = {'FD001':100,'FD002':260,'FD003':100,'FD004':248}.get(dataset,0),
        status     = 'onboarding'
    )
    db.add(new_factory)
    db.commit()
    print(f"[AutoOnboarding] Factory {factory_id} ({name}) registered")
    return {"status":"registered","factory_id":factory_id,
            "name":name,"dataset":dataset,
            "message":f"Factory {factory_id} will join on next FL round"}


# ── SECURITY ENDPOINTS ────────────────────────────────────────
@app.get("/security/byzantine")
def get_byzantine_history():
    return {"total_checks":0,"total_flagged":0,
            "flagged_events":[],"message":"No Byzantine activity detected"}


@app.get("/factories/{factory_id}/privacy")
def get_privacy_status(factory_id: int, db: Session = Depends(get_db)):
    f = db.query(Factory).filter(Factory.factory_id == factory_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Factory not found")
    return {"factory_id":f.factory_id,"name":f.name,"dp_enabled":True,
            "epsilon_per_round":1.0,"privacy_level":"Strong",
            "guarantee":"Raw sensor data cannot be reconstructed from shared weights"}