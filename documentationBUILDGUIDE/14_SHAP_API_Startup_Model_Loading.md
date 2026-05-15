# 14 — SHAP API: Startup & Model Loading (`shap_api.py` Part 1)

**File:** `machine_learning/notebooks/shap_api.py`  
**Run:** `uvicorn shap_api:app --port 8001 --reload`  
**URL:** `http://localhost:8001`  
**Currently running:** Yes (terminal shows it running for 11h+)

---

## Purpose

A standalone FastAPI service that hosts the per-factory CNN models and serves gradient saliency explanations to the Django dashboard's Explainability page. It runs separately from the FL backend (port 8000) because:
1. It needs to load 4 large `.pt` model files — slow startup, best isolated
2. The SHAP inference pipeline is CPU-intensive — benefits from separate process
3. Dashboard calls it independently of FL training status

---

## `FACTORY_CONFIG` — Per-Factory Model Registry

```python
FACTORY_CONFIG = {
    1: {
        'model':   'best_model_FD001.pt',
        'scaler':  'scaler_FD001.pkl',
        'data':    'train_FD001.txt',
        'sensors': [
            'sensor_2',  'sensor_3',  'sensor_4',  'sensor_7',
            'sensor_8',  'sensor_9',  'sensor_11', 'sensor_12',
            'sensor_13', 'sensor_14', 'sensor_15', 'sensor_17',
            'sensor_20', 'sensor_21'
        ],   # 14 sensors
        'name': 'Factory Mumbai (FD001)'
    },
    2: {
        'model':   'best_model_FD002.pt',
        'scaler':  'scaler_FD002.pkl',
        'data':    'train_FD002.txt',
        'sensors': [
            'sensor_1',  'sensor_2',  'sensor_3',  'sensor_4',  'sensor_5',
            'sensor_6',  'sensor_7',  'sensor_8',  'sensor_9',  'sensor_10',
            'sensor_11', 'sensor_12', 'sensor_13', 'sensor_14', 'sensor_15',
            'sensor_17', 'sensor_18', 'sensor_20', 'sensor_21'
        ],   # 19 sensors
        'name': 'Factory Berlin (FD002)'
    },
    3: {
        'model':   'best_model_FD003.pt',
        'scaler':  'scaler_FD003.pkl',
        'data':    'train_FD003.txt',
        'sensors': [
            'sensor_2',  'sensor_3',  'sensor_4',  'sensor_6',  'sensor_7',
            'sensor_8',  'sensor_9',  'sensor_10', 'sensor_11', 'sensor_12',
            'sensor_13', 'sensor_14', 'sensor_15', 'sensor_17', 'sensor_20',
            'sensor_21'
        ],   # 16 sensors
        'name': 'Factory Detroit (FD003)'
    },
    4: {
        'model':   'best_model_FD004.pt',
        'scaler':  'scaler_FD004.pkl',
        'data':    'train_FD004.txt',
        'sensors': [
            'sensor_1',  'sensor_2',  'sensor_3',  'sensor_4',  'sensor_5',
            'sensor_6',  'sensor_7',  'sensor_8',  'sensor_9',  'sensor_10',
            'sensor_11', 'sensor_12', 'sensor_13', 'sensor_14', 'sensor_15',
            'sensor_17', 'sensor_18', 'sensor_20', 'sensor_21'
        ],   # 19 sensors
        'name': 'Factory Tokyo (FD004)'
    },
}
```

**Key difference from FL production (`data_loader.py`):**  
The SHAP API uses per-factory sensor counts (14/19/16/19), whereas the FL client uses a fixed 14 sensors for all factories. This means the SHAP models were trained from the individual notebooks (NB01–NB04) — not the FL-production pipeline. Each factory's model is specifically tuned to its sensor set.

---

## Global Registries

```python
MODELS  = {}   # {factory_id: FailureCNN instance, eval mode}
SCALERS = {}   # {factory_id: fitted MinMaxScaler}
BG_DATA = {}   # {factory_id: torch.FloatTensor (10, 30, n_sensors)}
```

All populated at startup. Empty dict = model failed to load for that factory.

---

## `load_background_data()` — Fast Background Sample

```python
def load_background_data(filename, sensor_cols, max_engines=5):
    """
    Load a tiny background dataset for baseline reference.
    nrows=3000 reads only the first 3000 lines — extremely fast.
    Returns up to 10 windows of shape (30, n_sensors).
    """
    import pandas as pd
    from sklearn.preprocessing import MinMaxScaler

    all_sensors = ['sensor_' + str(i) for i in range(1, 22)]
    col_names   = ['engine_id', 'cycle', 'setting_1', 'setting_2', 'setting_3'] + all_sensors

    df = pd.read_csv(filename, sep=r'\s+', header=None, nrows=3000)
    df.columns = col_names

    # Normalize using a fresh scaler (background only — not for inference)
    scaler = MinMaxScaler()
    df[sensor_cols] = scaler.fit_transform(df[sensor_cols]).astype(np.float32)

    windows = []
    for eid in list(df['engine_id'].unique())[:max_engines]:
        edf  = df[df['engine_id'] == eid].sort_values('cycle')
        vals = edf[sensor_cols].values
        if len(vals) >= 30:
            windows.append(vals[:30])   # first 30 cycles = early-life baseline
        if len(windows) >= 10:
            break

    # Fallback: random noise if dataset can't be loaded
    if not windows:
        windows = [np.random.rand(30, len(sensor_cols)).astype(np.float32)]

    return np.array(windows, dtype=np.float32)   # (n_windows, 30, n_sensors)
```

**Why background data?**  
Background windows represent "normal operation" — early-life cycles of healthy engines. They serve as the baseline for saliency comparison: a sensor's importance is how much its value deviates from baseline behavior.

---

## `load_models()` — Startup Event

```python
@app.on_event("startup")
def load_models():
    """Load all factory models on startup. Called once when uvicorn starts."""
    print("\nLoading SHAP models...")
    for fid, cfg in FACTORY_CONFIG.items():
        try:
            sensor_cols = cfg['sensors']
            n           = len(sensor_cols)

            # 1. Load CNN model
            model = FailureCNN(n_sensors=n)
            model.load_state_dict(
                torch.load(cfg['model'], map_location='cpu', weights_only=True)
            )
            model.eval()
            MODELS[fid] = model

            # 2. Load MinMaxScaler
            with open(cfg['scaler'], 'rb') as f:
                SCALERS[fid] = pickle.load(f)

            # 3. Load background windows
            bg         = load_background_data(cfg['data'], sensor_cols=sensor_cols)
            BG_DATA[fid] = torch.FloatTensor(bg)

            print(f"  [OK] Factory {fid} ({cfg['name']}) -> {n} sensors loaded perfectly")

        except Exception as e:
            print(f"  [FAIL] Factory {fid} failed: {e}")
            # Factory stays absent from MODELS/SCALERS/BG_DATA
            # GET /factories will show "loaded": false for this factory

    print(f"Loaded {len(MODELS)}/4 models\n")
```

**What `weights_only=True` does:**  
PyTorch 2.0+ deprecation: `torch.load()` without `weights_only=True` can execute arbitrary Python via pickle (security risk). Setting `weights_only=True` restricts loading to only tensor data — the correct approach for loading model weights.

**Startup output (normal):**
```
Loading SHAP models...
  [OK] Factory 1 (Factory Mumbai (FD001)) -> 14 sensors loaded perfectly
  [OK] Factory 2 (Factory Berlin (FD002)) -> 19 sensors loaded perfectly
  [OK] Factory 3 (Factory Detroit (FD003)) -> 16 sensors loaded perfectly
  [OK] Factory 4 (Factory Tokyo (FD004)) -> 19 sensors loaded perfectly
Loaded 4/4 models
```

---

## Health Endpoints

```python
@app.get("/")
def health():
    return {
        "status":        "ok",
        "service":       "SHAP Explainability API",
        "models_loaded": list(MODELS.keys()),   # [1, 2, 3, 4] if all loaded
    }

@app.get("/factories")
def get_factories():
    return {
        fid: {
            "name":       cfg['name'],
            "loaded":     fid in MODELS,       # True/False
            "n_sensors":  len(cfg['sensors'])  # 14/19/16/19
        }
        for fid, cfg in FACTORY_CONFIG.items()
    }
```

**`GET /factories` response:**
```json
{
  "1": {"name": "Factory Mumbai (FD001)", "loaded": true, "n_sensors": 14},
  "2": {"name": "Factory Berlin (FD002)", "loaded": true, "n_sensors": 19},
  "3": {"name": "Factory Detroit (FD003)", "loaded": true, "n_sensors": 16},
  "4": {"name": "Factory Tokyo (FD004)", "loaded": true, "n_sensors": 19}
}
```

---

## `FailureCNN` — Inline Architecture

The SHAP API includes its own copy of `FailureCNN` (not imported from `client.model`) to keep it self-contained:

```python
class FailureCNN(nn.Module):
    def __init__(self, n_sensors=14):
        super().__init__()
        self.conv1   = nn.Conv1d(n_sensors, 32, kernel_size=3, padding=1)
        self.conv2   = nn.Conv1d(32, 64, kernel_size=3, padding=1)
        self.relu    = nn.ReLU()
        self.pool    = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(0.3)
        self.fc      = nn.Linear(64, 2)

    def forward(self, x):
        x = x.permute(0, 2, 1)              # (B,seq,sensors) → (B,sensors,seq)
        x = self.relu(self.conv1(x))        # → (B, 32, seq)
        x = self.relu(self.conv2(x))        # → (B, 64, seq)
        x = self.pool(x).squeeze(-1)        # → (B, 64)
        x = self.dropout(x)
        return self.fc(x)                   # → (B, 2)
```

Identical to `client/model.py` — allows loading the same `.pt` weight files.
