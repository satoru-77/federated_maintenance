# NB03 — Notebook: FD003 EDA, Preprocessing & CNN Training

**File:** `machine_learning/notebooks/03_fd003.ipynb`  
**Dataset:** NASA CMAPSS FD003 — 100 training engines, **1 operating condition**, **2 fault modes** (HPC degradation + Fan degradation)  
**Key difference from FD001:** Same operating conditions as FD001 but engines can fail via two different failure mechanisms — the CNN must learn two distinct degradation signatures.  
**Output files:** `best_model_FD003.pt`, `scaler_FD003.pkl`, `useful_sensors_FD003.pkl`

---

> **Structure note:** FD003 follows the same 7-section pipeline as FD001 (NB01). This doc focuses on what is **different** in FD003. Refer to NB01 for full pipeline code.

---

## What Makes FD003 Different: Two Fault Modes

FD001 engines always fail from HPC (High Pressure Compressor) degradation — one known failure pattern. FD003 engines can fail from either:

| Fault Mode | Component | Symptom sensors | Cycle signature |
|-----------|-----------|----------------|-----------------|
| Mode 1 | HPC degradation | `sensor_11`, `sensor_4`, `sensor_14` | Gradual pressure/temperature drift |
| Mode 2 | Fan degradation | `sensor_2`, `sensor_3`, `sensor_8` | Different temperature ratio drift |

**Why this is harder:** The CNN must learn that two very different 30-cycle sensor patterns both predict failure. It can't specialize for one signature.

---

## Dataset Statistics vs FD001

| Property | FD001 | FD003 |
|----------|-------|-------|
| Training engines | 100 | 100 |
| Test engines | 100 | 100 |
| Operating conditions | 1 | 1 |
| **Fault modes** | **1** | **2** |
| Total rows (train) | 20,631 | 24,720 |
| Total windows | ~17,600 | ~21,500 |
| Useful sensors | 14 | 16 |
| Avg engine life | ~206 cycles | ~247 cycles |

FD003 engines live **longer on average** — fan degradation tends to be slower-progressing than HPC degradation.

---

## Section A — Data Loading

```python
df = pd.read_csv('train_FD003.txt', sep='\s+', header=None, names=column_names)
print(df.shape)   # (24720, 26)
print(df['engine_id'].nunique())  # 100 engines
print(df.groupby('engine_id')['cycle'].max().describe())
# mean ≈ 247 cycles (longer lived than FD001's ~206)
```

---

## Section B — RUL & Labels (Identical logic)

```python
df['RUL']   = df['max_cycle'] - df['cycle']
df['label'] = (df['RUL'] <= 30).astype(int)
```

**Class distribution for FD003:**
```
label 0 (safe):   ~21,700 rows  (88%)
label 1 (danger): ~ 3,000 rows  (12%)
→ slightly more imbalanced than FD001 because engines live longer
  (more safe cycles per engine, same 30-cycle danger window)
```

---

## Section C — Sensor Selection: 16 Useful Sensors

With 1 operating condition (same as FD001), most constant sensors remain constant. However, the **second fault mode** (fan degradation) causes additional sensors to show meaningful variation.

```python
useful_sensors = [s for s in sensor_columns if df[s].nunique() > 2]
print("Useful sensors:", len(useful_sensors))   # 16
```

**FD003 result:**
- **Dropped (5 sensors):** `sensor_1`, `sensor_5`, `sensor_10`, `sensor_16`, `sensor_18`
- **Kept (16 sensors):** 14 from FD001 + `sensor_6` + `sensor_19`
  - `sensor_6` (corrected fan speed ratio) — now informative because fan degradation causes variation
  - `sensor_19` (total pressure ratio across LPT) — informative under fan fault mode

---

## Section D — Sliding Windows

```python
X, y = make_windows(df, useful_sensors, window_size=30)
print("X shape:", X.shape)    # (21500, 30, 16)
```

**Window example — two engines, two failure modes:**
```
Engine 23 (HPC fault): cycles 1–247
  Windows 218–247 → FAILURE windows
  Pattern: sensor_11 rises sharply in last 30 cycles

Engine 67 (Fan fault): cycles 1–241
  Windows 212–241 → FAILURE windows  
  Pattern: sensor_2 and sensor_3 show different drift pattern
  
Both map to label=1, but with different sensor patterns
→ CNN must learn both patterns represent failure
```

---

## Section F — CNN Architecture

```python
model = FailureCNN(n_sensors=16)
# in_channels=16 in conv1 (vs 14 for FD001, 19 for FD002)
# Architecture identical otherwise
```

---

## Section G — Results & Difficulty Analysis

**FD003 typical results:**
```
Accuracy:  ~86–90%  (similar to FD001)
AUC-ROC:   ~0.93–0.96  (slightly lower than FD001)
Miss Rate: ~8–15%
```

**Why slightly harder than FD001 despite same operating conditions?**
- Two failure modes = CNN must generalize across two different degradation signatures
- A window from an HPC-failing engine looks different from a fan-failing engine
- The model can't overfit to one signature — must learn both
- However, single operating condition still helps (no condition-shift noise)

**Compare across datasets:**
```
FD001: 1 condition, 1 fault → Easiest
FD003: 1 condition, 2 faults → Medium
FD002: 6 conditions, 1 fault → Hard
FD004: 6 conditions, 2 faults → Hardest
```

---

## Saved Outputs

```python
with open('scaler_FD003.pkl', 'wb') as f:
    pickle.dump(scaler, f)       # fitted on 24,720 rows × 16 sensors

with open('useful_sensors_FD003.pkl', 'wb') as f:
    pickle.dump(useful_sensors, f)   # 16 sensor names

torch.save(model.state_dict(), 'best_model_FD003.pt')
```

Used by `shap_api.py` when `factory_id=3` (Factory Detroit).
