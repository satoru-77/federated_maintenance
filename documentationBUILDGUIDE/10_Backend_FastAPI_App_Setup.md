# 10 — Backend: FastAPI App Setup, CORS & WebSocket Manager (`main.py` Part 1)

**File:** `fl_backend/backend/main.py`  
**Run:** `uvicorn backend.main:app --reload --port 8000`  
**URL:** `http://localhost:8000`  
**Auto-docs:** `http://localhost:8000/docs` (Swagger UI, auto-generated)

---

## App Initialization

```python
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio, json

app = FastAPI(
    title       = "FL Predictive Maintenance API",
    description = "Federated Learning system for industrial engine failure prediction",
    version     = "1.0.0"
)
```

### CORS Middleware

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],   # allows Django dashboard (port 8002) to call this API
    allow_methods = ["*"],   # GET, POST, etc.
    allow_headers = ["*"],
)
```

**Why CORS is required:**  
The Django dashboard (port 8002) makes XHR/fetch calls to this API (port 8000). Browsers block cross-origin requests by default. `CORSMiddleware` adds `Access-Control-Allow-Origin: *` to every response, allowing the browser to permit these requests.

**Production note:** `allow_origins=["*"]` should be changed to `["http://localhost:8002"]` before public deployment.

### Startup Event

```python
@app.on_event("startup")
def startup():
    """Runs once when FastAPI starts. Creates DB tables if they don't exist."""
    create_tables()
    print("FastAPI started. Database ready.")
```

Calls `db.create_tables()` → `Base.metadata.create_all(bind=engine)` → safe idempotent table creation.

---

## `ConnectionManager` — WebSocket Connection Pool

```python
class ConnectionManager:
    """
    Manages all active WebSocket connections.
    
    When a browser opens the dashboard → connects to /ws → added to pool.
    When FL server completes a round  → POST /ws/broadcast → all browsers notified.
    """
    def __init__(self):
        self.active_connections: list[WebSocket] = []
```

### `connect()` — Accept and Register

```python
async def connect(self, websocket: WebSocket):
    await websocket.accept()                        # complete WS handshake
    self.active_connections.append(websocket)       # add to pool
    print(f"[WS] Client connected. Total: {len(self.active_connections)}")
```

### `disconnect()` — Remove from Pool

```python
def disconnect(self, websocket: WebSocket):
    self.active_connections.remove(websocket)
    print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")
```

### `broadcast()` — Push to All Browsers

```python
async def broadcast(self, message: dict):
    """Send a JSON message to ALL connected browsers."""
    if not self.active_connections:
        return
    text = json.dumps(message)
    disconnected = []
    for connection in self.active_connections:
        try:
            await connection.send_text(text)
        except Exception:
            disconnected.append(connection)   # track stale connections
    for conn in disconnected:
        self.active_connections.remove(conn)  # clean up closed sockets
```

**Why catch exceptions per-connection?**  
If a browser tab closes without proper disconnect, the WebSocket raises on `send_text()`. Instead of crashing the broadcast, we collect stale connections and remove them after iteration (cannot modify list during iteration).

---

## WebSocket Endpoint: `/ws`

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Browser connects here on dashboard load.
    Server pushes JSON events after each FL round.
    Connect with: ws://localhost:8000/ws
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()  # blocks until browser sends
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            # Any other message is ignored — this is a push-only channel
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

**Connection lifecycle:**
```
Browser loads overview.html
    ↓ JS: new WebSocket('ws://localhost:8000/ws')
    ↓ WebSocket handshake
    ↓ manager.connect(ws) — added to pool

Browser tab open (indefinitely)
    ↓ FL round completes → POST /ws/broadcast
    ↓ manager.broadcast() → ws.send_text(event_json)
    ↓ Browser receives JSON → updates chart, logs event

Browser tab closes
    ↓ WebSocketDisconnect raised in receive_text()
    ↓ manager.disconnect(ws) — removed from pool
```

## Internal Broadcast Trigger: `POST /ws/broadcast`

```python
@app.post("/ws/broadcast")
async def broadcast_event(event: dict):
    """
    Internal endpoint — called by FL server (db_logger.py) after each round.
    Broadcasts the event to all connected dashboard browsers.
    """
    await manager.broadcast(event)
    return {"status": "broadcast", "connections": len(manager.active_connections)}
```

**Who calls this?**  
`db_logger._broadcast_round_event()` calls `requests.post("http://localhost:8000/ws/broadcast", ...)` synchronously from the Flower server process. The FL server is a separate process — it cannot call `manager.broadcast()` directly (different memory space). The HTTP POST bridges the two processes.

```
FL Server process (port 8080)               FastAPI process (port 8000)
────────────────────────────                ──────────────────────────────
aggregate_fit() completes
  → log_round()
    → _broadcast_round_event()
      → requests.post(                  →→→  POST /ws/broadcast
           "http://localhost:8000/          → manager.broadcast(event)
            ws/broadcast",                    → all connected browsers
           json=event, timeout=1)              receive the event JSON
```

---

## All REST Endpoint Summary

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | Health check |
| GET | `/factories` | All 4 factories |
| GET | `/factories/{id}` | One factory + last 20 rounds |
| GET | `/factories/{id}/alpha` | Factory's best alpha value |
| GET | `/rounds` | Training rounds (filterable) |
| GET | `/clusters` | Current cluster assignments |
| GET | `/clusters/history` | Cluster change log |
| GET | `/experiments` | All experiment runs |
| GET | `/round-summaries` | Per-round dual accuracy metrics |
| GET | `/metrics` | Session-scoped summary stats |
| WS | `/ws` | WebSocket live event stream |
| POST | `/ws/broadcast` | Internal: push event to browsers |
| POST | `/sim/start` | Launch FL PowerShell terminals |
| POST | `/sim/stop` | Kill FL processes |
| POST | `/sim/speed` | Set simulation speed |
| POST | `/sim/inject` | Inject demo scenario |
| POST | `/factories/register` | Auto-onboard new factory |
| GET | `/security/byzantine` | Byzantine flag history |
| GET | `/factories/{id}/privacy` | Factory DP status |
