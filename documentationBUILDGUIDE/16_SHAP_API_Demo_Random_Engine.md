# 16 — SHAP API: `/explain/demo` — Random Engine Selection (`shap_api.py` Part 3)

**File:** `machine_learning/notebooks/shap_api.py` (lines 291–377)  
**Endpoint:** `POST /explain/demo?factory_id=1&scenario=random`  
**Called by:** Django `explainability` view → JavaScript fetch on "Analyze Engine" button click

---

## Endpoint Signature

```python
@app.post("/explain/demo")
def explain_demo(factory_id: int = 1, scenario: str = "critical"):
    """
    Demo endpoint — generates sensor windows for the dashboard.
    
    Query params:
        factory_id: int  (1–4)
        scenario:   str  ("random" | "healthy" | "degraded" | "critical")
    
    For "random": loads real test data, picks a real engine, returns real CNN inference.
    For others:   constructs synthetic numpy arrays and calls /explain internally.
    """
```

**Django calls this as:**
```python
response = requests.post(
    f"http://localhost:8001/explain/demo",
    params={"factory_id": factory_id, "scenario": "random"}
)
```

---

## Branch 1: `scenario == "random"` — Real Test Data Engine

This is the academically important branch. It loads actual NASA CMAPSS test data and runs real CNN inference.

```python
if scenario == "random":
    import pandas as pd, pickle, random

    # ── File paths (relative to shap_api.py's working directory) ──
    test_file   = f'test_FD00{factory_id}.txt'   # e.g. "test_FD001.txt"
    rul_file    = f'RUL_FD00{factory_id}.txt'    # e.g. "RUL_FD001.txt"
    scaler_file = f'scaler_FD00{factory_id}.pkl'

    # ── Load all 26 columns ────────────────────────────────────
    all_sensors = ['sensor_' + str(i) for i in range(1, 22)]
    col_names   = ['engine_id', 'cycle', 'setting_1', 'setting_2', 'setting_3'] + all_sensors
    df_raw = pd.read_csv(test_file, sep=r'\s+', header=None, names=col_names)
    df     = df_raw.copy()

    # ── Scale only the useful sensors for this factory ─────────
    with open(scaler_file, 'rb') as f:
        scaler = pickle.load(f)
    df[sensor_cols] = scaler.transform(df[sensor_cols])
    # Note: .transform() not .fit_transform() — use the scaler fitted on TRAINING data
    # This ensures test data is normalized identically to how the model was trained
```

### Random Engine Selection

```python
    # Find engines with at least 30 cycles (can form a complete window)
    engine_counts = df['engine_id'].value_counts()
    valid_engines = engine_counts[engine_counts >= 30].index.tolist()

    random_engine = random.choice(valid_engines)
    # Each call returns a different engine — dashboard shows variety

    edf     = df[df['engine_id'] == random_engine].sort_values('cycle')
    edf_raw = df_raw[df_raw['engine_id'] == random_engine].sort_values('cycle')
    vals    = edf[sensor_cols].values    # scaled values, shape (n_cycles, n_sensors)
    cycles  = edf['cycle'].values        # cycle numbers for metadata display
```

### Random Window Within the Engine

```python
    max_start = len(vals) - 30          # last valid start position
    start_idx = random.randint(0, max_start)
    fake_window = vals[start_idx : start_idx + 30].astype(np.float32)
    # Shape: (30, n_sensors) — a real 30-cycle window from a real engine
```

**Why "random window" within the engine?**  
The test file contains only the last few cycles per engine (not the full life). Using a random start position within those cycles ensures each dashboard click shows a different temporal snapshot — early cycles look different from late cycles (approaching failure). This makes the demo genuinely educational.

### Ground Truth Lookup

```python
    # RUL_FD001.txt: one RUL value per engine (the final RUL at end of test sequence)
    rul_df       = pd.read_csv(rul_file, header=None, names=['RUL'])
    actual_rul   = int(rul_df.iloc[random_engine - 1]['RUL'])
    # Index = engine_id - 1 (engines are 1-indexed, pandas is 0-indexed)

    actual_label = "FAILURE" if actual_rul <= 30 else "HEALTHY"
    # Same threshold as training: RUL ≤ 30 cycles = failure imminent
```

### Raw Sensor Sample for Display

```python
    # First raw (unscaled) row of the window — shown in "Live Data Verification" panel
    raw_row = edf_raw.iloc[start_idx][sensor_cols].to_dict()
    raw_sensor_sample = {k: round(float(v), 4) for k, v in raw_row.items()}
    # e.g. {"sensor_2": 641.8200, "sensor_3": 1589.0000, "sensor_11": 47.4900, ...}
    # These are the actual physical sensor values before normalization
```

### Build Request and Call `/explain`

```python
    req = ExplainRequest(
        factory_id    = factory_id,
        sensor_window = fake_window.tolist(),   # scaled (30, n_sensors) as list
        scenario      = scenario,               # "random"
        actual_rul    = actual_rul,
        actual_label  = actual_label,
        engine_id           = int(random_engine),
        dataset_file        = test_file,
        rul_file            = rul_file,
        start_cycle         = int(cycles[start_idx]),
        end_cycle           = int(cycles[start_idx + 29]),
        total_engine_cycles = int(len(cycles)),
        sensor_columns      = list(sensor_cols),
        raw_sensor_sample   = raw_sensor_sample,
    )
    return explain(req)   # internally calls POST /explain logic
```

---

## Branch 2: Synthetic Scenarios

```python
elif scenario == "healthy":
    np.random.seed(101)
    fake_window = (np.random.rand(30, n).astype(np.float32) * 0.25) + 0.05
    # Values in [0.05, 0.30] — low normalized values = healthy engine
    # Seed fixed so same result every call — reproducible demo

elif scenario == "degraded":
    np.random.seed(202)
    fake_window = (np.random.rand(30, n).astype(np.float32) * 0.4) + 0.1
    # Values in [0.10, 0.50] — moderate values = degrading engine

else:  # "critical"
    np.random.seed(42)
    fake_window = (np.random.rand(30, n).astype(np.float32) * 0.5) + 0.3
    # Values in [0.30, 0.80] — high values = critical state
    
    # Spike the two sensors most likely to drive failure (index 0 and 2)
    fake_window[:, 0] += 0.4   # sensor_2 (index 0): +40% — temperature spike
    fake_window[:, 2] += 0.4   # sensor_4 (index 2): +40% — pressure spike
    # Values now in [0.70, 1.20] for these sensors — well above normal range

req = ExplainRequest(
    factory_id    = factory_id,
    sensor_window = fake_window.tolist(),
    scenario      = scenario,
    # No metadata for synthetic scenarios
)
return explain(req)
```

**Fixed seeds for synthetic scenarios:**  
`np.random.seed(101/202/42)` ensures the healthy/degraded/critical scenarios always generate the same windows → same saliency → same explanation text. This makes the dashboard demo consistent and repeatable.

---

## Data Flow: Dashboard → SHAP API → CNN → Response

```
User clicks factory button + "Analyze Engine":
    Django view:
        GET params: factory_id=1, scenario=random
        requests.post("http://localhost:8001/explain/demo?factory_id=1&scenario=random")
    
    explain_demo(factory_id=1, scenario="random"):
        Load test_FD001.txt (scaled)
        Pick random engine e.g. engine_47
        Pick random start cycle e.g. cycle 183
        Extract window: vals[183:213] shape (30, 14)
        Load RUL_FD001.txt → actual_rul = 18 → actual_label = "FAILURE"
        Extract raw_sensor_sample: {"sensor_2": 641.8, ...}
        
        → calls explain(ExplainRequest(...))
    
    explain():
        x_tensor = FloatTensor(window).unsqueeze(0)  # (1, 30, 14)
        model(x_tensor) → probs = [0.217, 0.783]     # P(FAILURE) = 0.783
        gradient saliency → sv[14]
        sv signs aligned (failure case → all positive)
        
        → SHAPResponse:
            prediction = "FAILURE"
            confidence = 0.7832
            top_sensors = ["sensor_11", "sensor_8", "sensor_17"]
            shap_values = {"sensor_11": 0.00027, ...}
            actual_rul = 18
            raw_sensor_sample = {"sensor_2": 641.82, ...}
    
    Django view:
        Renders explainability.html with response data
        
    Browser:
        Prediction badge → "FAILURE" (red)
        Confidence → 78.3%
        SHAP waterfall → sensor_11 longest bar
        Live data table → actual sensor values from raw_sensor_sample
        Ground truth → "RUL = 18 cycles → FAILURE"
```

---

## Why Two-Tier Design (`/explain/demo` → `/explain`)?

```
/explain/demo   = data preparation layer (generates the window)
/explain        = inference layer (runs CNN + saliency)

Benefits:
1. /explain can be called directly with any custom sensor window
   (future: maintenance engineer pastes real sensor readings)
   
2. /explain/demo handles the complexity of loading test files,
   picking random engines, building ExplainRequest objects
   
3. Separation of concerns: demo logic never bleeds into inference logic
```
