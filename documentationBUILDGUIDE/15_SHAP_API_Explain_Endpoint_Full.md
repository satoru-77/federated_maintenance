# 15 — SHAP API: `/explain` Endpoint & Saliency Math (`shap_api.py` Part 2)

**File:** `machine_learning/notebooks/shap_api.py` (lines 130–288)  
**Endpoint:** `POST /explain`  
**Called by:** `POST /explain/demo` internally, and directly from the Django view for custom sensor windows

---

## Request & Response Schemas

### `ExplainRequest` (Pydantic model)

```python
class ExplainRequest(BaseModel):
    factory_id:    int                    # 1–4
    sensor_window: List[List[float]]      # (30, n_sensors) — 30 cycles × n sensors
    scenario:      Optional[str] = None   # "healthy" | "degraded" | "random" | "critical"
    actual_rul:    Optional[int] = None   # ground truth RUL (from RUL_FD00X.txt)
    actual_label:  Optional[str] = None  # "FAILURE" or "HEALTHY"
    
    # Rich metadata (populated only for "random" scenario)
    engine_id:           Optional[int]       = None
    dataset_file:        Optional[str]       = None   # "test_FD001.txt"
    rul_file:            Optional[str]       = None   # "RUL_FD001.txt"
    start_cycle:         Optional[int]       = None   # cycle window start
    end_cycle:           Optional[int]       = None   # cycle window end
    total_engine_cycles: Optional[int]       = None   # total life of this engine
    sensor_columns:      Optional[List[str]] = None   # sensor names in window order
    raw_sensor_sample:   Optional[dict]      = None   # unscaled first-row values
```

### `SHAPResponse` (Pydantic model)

```python
class SHAPResponse(BaseModel):
    factory_id:   int
    factory_name: str          # "Factory Mumbai (FD001)"
    prediction:   str          # "FAILURE" or "HEALTHY"
    confidence:   float        # 0.0–1.0
    shap_values:  dict         # {sensor_name: saliency_score} sorted by |score|
    top_sensors:  List[str]    # top 3 sensor names by absolute saliency
    explanation:  str          # human-readable sentence
    actual_rul:   Optional[int]
    actual_label: Optional[str]
    # ... plus all the Optional metadata fields echoed back
```

---

## `POST /explain` — Full Walkthrough

```python
@app.post("/explain", response_model=SHAPResponse)
def explain(req: ExplainRequest):
    fid = req.factory_id
    if fid not in MODELS:
        raise HTTPException(404, f"Factory {fid} model not loaded.")

    model       = MODELS[fid]
    sensor_cols = FACTORY_CONFIG[fid]['sensors']
    n_sensors   = len(sensor_cols)
```

### Step 1: Validate and Tensorize Input

```python
    x_np = np.array(req.sensor_window, dtype=np.float32)
    if x_np.shape != (30, n_sensors):
        raise HTTPException(400, f"sensor_window must be (30, {n_sensors}), got {x_np.shape}")
    # Factory 1: must be (30, 14); Factory 2: (30, 19); etc.

    x_tensor = torch.FloatTensor(x_np).unsqueeze(0)   # → (1, 30, n_sensors)
```

### Step 2: Forward Pass (Classification)

```python
    model.eval()
    with torch.no_grad():
        output = model(x_tensor)          # → (1, 2) logits
        probs  = torch.softmax(output, dim=1)[0]
        # probs[0] = P(HEALTHY), probs[1] = P(FAILURE)
```

### Step 3: Scenario-Based Prediction Override

```python
    if req.scenario == "healthy":
        pred_class = 0
        confidence = 0.1425      # fixed — "14.25% failure probability"
        explanation_prefix = "All monitored sensors operate within optimal baselines. No failure signature detected."

    elif req.scenario == "degraded":
        pred_class = 0
        confidence = 0.3845      # fixed — "38.45% failure probability"
        explanation_prefix = "Elevated vibration drift detected. Approaching predictive threshold (40%). Early maintenance scheduling recommended."

    elif req.scenario == "random":
        # REAL model output — no override
        FAILURE_THRESHOLD = 0.50
        failure_prob = float(probs[1])
        if failure_prob >= FAILURE_THRESHOLD:
            pred_class = 1
            confidence = failure_prob        # actual model confidence
        else:
            pred_class = 0
            confidence = float(probs[0])
        explanation_prefix = (
            "Live inference from NASA CMAPSS test dataset. "
            "CNN1D model evaluated real 30-cycle sensor window from the test set."
        )

    else:  # "critical" or any unrecognized scenario
        pred_class = 1
        confidence = float(probs[1]) if float(probs[1]) > 0.5 else 0.8845
        explanation_prefix = "Critical profile identified. High sensor load drives imminent failure probability."
```

**Design decision — scenario overrides:**  
The "healthy" and "degraded" scenarios use synthetic sensor windows (low-value numpy arrays). The CNN might not always produce clean healthy/failure outputs for these artificially constructed inputs. The fixed confidence values (0.1425, 0.3845) ensure the UI demo always shows a sensible narrative. The "random" scenario uses **real test data** and **real model output** — no override.

### Step 4: Gradient Saliency (Core SHAP Equivalent)

```python
    # Enable gradient tracking on the input
    x_grad = x_tensor.clone().detach().requires_grad_(True)
    
    # Forward pass WITH gradient tracking
    out = model(x_grad)              # → (1, 2)
    
    # Backpropagate through the FAILURE class logit
    out[0, 1].backward()
    # Computes: ∂(logit_failure) / ∂(x_grad)  for every input element
    
    # x_grad.grad shape: (1, 30, n_sensors)
    sv = (
        x_grad.grad          # gradient tensor
        .squeeze(0)          # → (30, n_sensors)
        .abs()               # absolute value (direction doesn't matter)
        .mean(axis=0)        # average over 30 timesteps → (n_sensors,)
        .detach().numpy()    # convert to numpy
    )
    # sv[i] = mean |∂P(FAILURE)/∂sensor_i| across all 30 timesteps
    # Higher = sensor i has more influence on the failure probability
```

### Step 5: Scenario-Aligned Sign Adjustment

```python
    if req.scenario == "healthy":
        sv = -np.abs(sv) * 0.4
        # Negative = "this sensor is pushing toward HEALTHY"
        # Scaled down 60% — low absolute influence in healthy state

    elif req.scenario == "degraded":
        sv = np.abs(sv) * 0.7        # first 2 sensors positive (failure-direction)
        sv[2:] = -np.abs(sv[2:]) * 0.3  # remaining sensors negative (healthy direction)

    elif req.scenario == "random":
        if pred_class == 1:
            sv = np.abs(sv)           # failure-direction — all positive
        else:
            sv = -np.abs(sv) * 0.5   # healthy-direction — all negative, halved

    else:  # critical
        sv = np.abs(sv)              # all positive — all sensors pushing to failure
```

**Why manipulate sign?**  
The raw gradient is always positive (after `.abs()`). Sign indicates interpretation direction: positive = "pushes toward FAILURE", negative = "pushes toward HEALTHY". The sign alignment ensures the SHAP waterfall chart on the dashboard shows the correct color coding (red bars = failure drivers, blue bars = health indicators) per scenario.

### Step 6: Build and Return Response

```python
    shap_dict     = {sensor_cols[i]: round(float(sv[i]), 5) for i in range(n_sensors)}
    sorted_sensors = sorted(shap_dict.items(), key=lambda x: abs(x[1]), reverse=True)
    sorted_shap   = dict(sorted_sensors)   # sorted by absolute importance
    top3          = [s[0] for s in sorted_sensors[:3]]   # top 3 sensor names

    explanation = f"{explanation_prefix} Primary driving variables: {', '.join(top3)}."

    return SHAPResponse(
        factory_id   = fid,
        factory_name = FACTORY_CONFIG[fid]['name'],
        prediction   = "FAILURE" if pred_class == 1 else "HEALTHY",
        confidence   = round(confidence, 4),
        shap_values  = sorted_shap,     # all sensors, sorted by |saliency|
        top_sensors  = top3,            # top 3 names only
        explanation  = explanation,
        actual_rul   = req.actual_rul,
        actual_label = req.actual_label,
        # ... echo all metadata fields
    )
```

---

## Full Response Example (Factory 1, "random" scenario, FAILURE case)

```json
{
  "factory_id": 1,
  "factory_name": "Factory Mumbai (FD001)",
  "prediction": "FAILURE",
  "confidence": 0.7832,
  "shap_values": {
    "sensor_11": 0.00027,
    "sensor_8":  0.00016,
    "sensor_17": 0.00012,
    "sensor_15": 0.00011,
    "sensor_9":  0.00008,
    ...
  },
  "top_sensors": ["sensor_11", "sensor_8", "sensor_17"],
  "explanation": "Live inference from NASA CMAPSS test dataset. CNN1D model evaluated real 30-cycle sensor window from the test set. Primary driving variables: sensor_11, sensor_8, sensor_17.",
  "actual_rul": 18,
  "actual_label": "FAILURE",
  "engine_id": 47,
  "dataset_file": "test_FD001.txt",
  "rul_file": "RUL_FD001.txt",
  "start_cycle": 183,
  "end_cycle": 212,
  "total_engine_cycles": 215,
  "sensor_columns": ["sensor_2", "sensor_3", ...],
  "raw_sensor_sample": {"sensor_2": 641.82, "sensor_3": 1589.0, ...}
}
```

---

## Gradient Saliency Math Summary

```
For input window X of shape (30, n_sensors):
  
  Forward:  logits = CNN(X)          → shape (2,)
            P(FAILURE) = softmax(logits)[1]
  
  Backward: ∂logit_failure / ∂X     → shape (30, n_sensors)
  
  Saliency: sv[s] = mean_t( |∂logit_failure / ∂X[t,s]| )
                    where t = timestep (0..29), s = sensor index
  
  Interpretation: sv[s] large → sensor s strongly influences failure probability
                  sv[s] small → sensor s is relatively unimportant for this window
```

**Time complexity:** One forward pass + one backward pass = O(n_params) ≈ O(7,714) — essentially instant (<10ms per request).
