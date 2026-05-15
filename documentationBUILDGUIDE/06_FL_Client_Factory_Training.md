# 06 — FL Client: Factory Training (`client.py`)

**File:** `fl_backend/client/client.py`  
**Class:** `FactoryClient(fl.client.NumPyClient)`  
**Launch:** `python -m client.client --factory-id 1` (run once per factory)  
**Connects to:** Flower server at `localhost:8080` via gRPC

---

## Overview: One Client = One Factory

```
Factory 1 (Mumbai)  → FactoryClient(factory_id=1) → connects to server:8080
Factory 2 (Berlin)  → FactoryClient(factory_id=2) → connects to server:8080
Factory 3 (Detroit) → FactoryClient(factory_id=3) → connects to server:8080
Factory 4 (Tokyo)   → FactoryClient(factory_id=4) → connects to server:8080
```

All 4 run as separate Python processes (separate terminals or `start_fl.ps1`). They never communicate with each other — only with the server.

---

## `__init__()` — Startup

```python
class FactoryClient(fl.client.NumPyClient):
    def __init__(self, factory_id):
        self.factory_id = factory_id
        self.n_sensors  = FACTORY_SENSORS[factory_id]  # {1:14, 2:19, 3:16, 4:19}

        # ── 1. Load this factory's dataset ──────────────────────
        (self.X_train, self.X_val,
         self.y_train, self.y_val,
         self.scaler, self.sensors) = load_factory_data(
            factory_id, data_dir="./client"
        )
        self.n_sensors = len(self.sensors)   # overrides FACTORY_SENSORS — uses actual count
        # n_sensors = 14 for all factories (FIXED_SENSORS in data_loader.py)

        # ── 2. Create model ──────────────────────────────────────
        self.model = FailureCNN(n_sensors=self.n_sensors, seq_length=30)
        # Fresh model — weights will be overwritten by server in first round

        # ── 3. Loss function ─────────────────────────────────────
        self.criterion = nn.CrossEntropyLoss(
            weight=torch.tensor([1.0, 5.0])
            # FAILURE class weighted 5× more than HEALTHY
            # Hardcoded here (vs computed from data in notebooks)
        )
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)

        # ── 4. Pre-convert tensors ───────────────────────────────
        self.X_train_t = torch.FloatTensor(self.X_train)
        self.y_train_t = torch.LongTensor(self.y_train)
        self.X_val_t   = torch.FloatTensor(self.X_val)
        self.y_val_t   = torch.LongTensor(self.y_val)
        # Converted once at startup → not re-converted every round (faster)

        # ── 5. Differential Privacy ──────────────────────────────
        self.dp = DifferentialPrivacy(epsilon=1.0, delta=1e-5, sensitivity=0.001)
        # DP noise added to weights before transmission
```

---

## `get_parameters()` — Send Weights to Server

```python
def get_parameters(self, config):
    """
    Return model weights with differential privacy noise added.
    Called by Flower: (a) at start of training, (b) after fit()
    """
    raw_weights = [
        val.cpu().numpy()
        for val in self.model.state_dict().values()
    ]
    # state_dict().values() = list of tensors: [conv1.weight, conv1.bias, conv2.weight, ...]

    # ── BYZANTINE ATTACK INJECTION (for simulation demo) ──────────
    if os.path.exists("byzantine_flag.txt"):
        with open("byzantine_flag.txt", "r") as f:
            rogue_id = f.read().strip()
        if str(self.factory_id) == rogue_id:
            print(f"[Factory {self.factory_id}] BYZANTINE: sending corrupted weights!")
            raw_weights = [w * 500 + 100 for w in raw_weights]
            # Massively inflated weights → will be detected by Byzantine detector
            os.remove("byzantine_flag.txt")   # fire once only

    return self.dp.add_noise(raw_weights)   # adds Gaussian noise for DP
```

**Byzantine attack mechanism:**  
The simulation writes `byzantine_flag.txt` with a factory ID. When that factory calls `get_parameters()`, it multiplies all weights by 500 and adds 100 — a massive outlier. The server's `ByzantineDetector` computes cosine similarity to the median weight vector; this corrupted vector will have near-zero similarity and get excluded.

---

## `set_parameters()` — Receive Weights from Server

```python
def set_parameters(self, parameters):
    """
    Load server-sent weights into local model.
    Called at the start of each round before local training.
    """
    params_dict = zip(self.model.state_dict().keys(), parameters)
    state_dict  = OrderedDict(
        {k: torch.tensor(v) for k, v in params_dict}
    )
    self.model.load_state_dict(state_dict, strict=True)
    # strict=True: all keys must match — fails if architecture changed
```

**What `parameters` is:**  
A list of numpy arrays from the server (the FedAvg-aggregated global weights or cluster weights). This overwrites the model's current weights entirely.

---

## `fit()` — Local Training (Core FL Step)

```python
def fit(self, parameters, config):
    """
    1. Load server weights into model
    2. Train locally for N epochs
    3. Return updated weights + metrics
    """
    self.set_parameters(parameters)              # load server weights
    local_epochs = config.get("local_epochs", 5) # from server's on_fit_config_fn

    # ── LOCAL TRAINING ────────────────────────────────────────────
    self.model.train()
    for epoch in range(local_epochs):            # 10 epochs per round
        self.optimizer.zero_grad()
        outputs = self.model(self.X_train_t)     # forward pass
        loss    = self.criterion(outputs, self.y_train_t)  # weighted CrossEntropy
        loss.backward()                          # backprop
        self.optimizer.step()                    # Adam update

    # ── VALIDATION ────────────────────────────────────────────────
    self.model.eval()
    with torch.no_grad():
        val_out = self.model(self.X_val_t)
        probs   = torch.softmax(val_out, dim=1)[:, 1].numpy()
        preds   = (probs > 0.4).astype(int)     # threshold 0.4, not 0.5!
        accuracy = float((preds == self.y_val).mean())

    # ── RETURN ────────────────────────────────────────────────────
    return (
        self.get_parameters(config={}),  # updated weights (with DP noise)
        len(self.X_train),               # n_samples (used for FedAvg weighting)
        {
            "factory_id": float(self.factory_id),
            "loss":       float(loss.item()),
            "accuracy":   float(accuracy)
        }
        # metrics dict goes to server → aggregate_fit() extracts them
    )
```

**Key: threshold = 0.4, not 0.5**  
`preds = (probs > 0.4).astype(int)` — lowered threshold biases toward predicting FAILURE. More false alarms, fewer missed failures. Appropriate for safety-critical maintenance where a missed failure is worse than a false alarm.

**Full-batch training:**  
`model(self.X_train_t)` processes **all training windows at once** (not mini-batches). This is simple but memory-intensive. Works because datasets are <150MB per factory at float32.

---

## `evaluate()` — Global Model Evaluation

```python
def evaluate(self, parameters, config):
    """
    Server sends GLOBAL weights → client tests on LOCAL val data → reports back.
    Measures how the global model performs on each factory's distribution.
    """
    self.set_parameters(parameters)   # load global (not clustered) weights
    self.model.eval()

    with torch.no_grad():
        outputs  = self.model(self.X_val_t)
        loss     = self.criterion(outputs, self.y_val_t)
        probs    = torch.softmax(outputs, dim=1)[:, 1].numpy()
        preds    = (probs > 0.4).astype(int)

    accuracy = float((preds == self.y_val).mean())

    return (
        float(loss.item()),          # loss scalar (Flower's first return val)
        len(self.X_val),             # n_examples (used for weighted avg)
        {"accuracy": accuracy}       # metrics (goes to aggregate_evaluate)
    )
```

---

## One Full Round from the Client Perspective

```
Server → broadcasts global weights to all clients
    ↓
fit(global_weights, config={"local_epochs": 10}) called
    ↓
  set_parameters(global_weights)       ← overwrite local model
  train for 10 epochs on local data    ← gradient descent, local only
  validate on local val set
    ↓
  get_parameters() → add DP noise → return updated weights
    ↓
  return (noisy_weights, n_train_samples, {factory_id, loss, accuracy})
    ↓
Server collects weights from all 4 clients → FedAvg
    ↓
evaluate(new_global_weights) called (possibly different round)
    ↓
  set_parameters(new_global_weights)
  test on local val data
    ↓
  return (loss, n_val_samples, {accuracy})
    ↓
Server logs round_summary → broadcasts WebSocket event
```

---

## `main()` — Client Entry Point

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-id",    type=int, required=True, choices=[1,2,3,4])
    parser.add_argument("--server-address", type=str, default="localhost:8080")
    args = parser.parse_args()

    client = FactoryClient(factory_id=args.factory_id)

    fl.client.start_numpy_client(
        server_address=args.server_address,
        client=client
    )
    # Connects to server:8080 via gRPC, waits for instructions
    # Runs indefinitely until all rounds are complete (server closes connection)
```

**Launch command per factory:**
```powershell
# Terminal 1
python -m client.client --factory-id 1

# Terminal 2
python -m client.client --factory-id 2

# Terminal 3
python -m client.client --factory-id 3

# Terminal 4
python -m client.client --factory-id 4
```

Or via `start_fl.ps1` which opens all 4 in separate PowerShell windows.
