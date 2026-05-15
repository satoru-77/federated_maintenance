# NB04 — Notebook: FD004 EDA, Preprocessing & CNN Training

**File:** `machine_learning/notebooks/04_fd004.ipynb`  
**Dataset:** NASA CMAPSS FD004 — 248 training engines, **6 operating conditions**, **2 fault modes** (hardest dataset)  
**Key difference:** Combines both challenges — multiple operating conditions AND multiple failure modes.  
**Output files:** `best_model_FD004.pt`, `scaler_FD004.pkl`, `useful_sensors_FD004.pkl`

---

> **Structure note:** FD004 follows the same 7-section pipeline as FD001 (NB01). This doc focuses on what is **different**. Refer to NB01 for full pipeline code.

---

## What Makes FD004 the Hardest Dataset

FD004 combines both challenges that make FD002 and FD003 harder than FD001:

| Challenge | FD001 | FD002 | FD003 | FD004 |
|-----------|-------|-------|-------|-------|
| Multiple op conditions | ✗ | ✅ | ✗ | ✅ |
| Multiple fault modes | ✗ | ✗ | ✅ | ✅ |
| **Combined difficulty** | **Lowest** | **Medium** | **Medium** | **Highest** |

The CNN must simultaneously:
1. Learn to ignore operating-condition-driven sensor variation (6 conditions)
2. Distinguish two different failure mode patterns within those 6 conditions
3. Generalize across 248 different engines with varying wear rates

---

## Dataset Statistics

| Property | FD001 | FD004 |
|----------|-------|-------|
| Training engines | 100 | 248 |
| Test engines | 100 | 248 |
| Operating conditions | 1 | 6 |
| Fault modes | 1 | 2 |
| Total rows (train) | 20,631 | 61,249 |
| Total windows | ~17,600 | ~54,000 |
| Useful sensors | 14 | 19 |
| Avg engine life | ~206 cycles | ~247 cycles |

FD004 is the **largest dataset** in the project (61,249 training rows). Factory Tokyo has the most training data.

---

## Section A — Data Loading

```python
df = pd.read_csv('train_FD004.txt', sep='\s+', header=None, names=column_names)
print(df.shape)    # (61249, 26)
print(df['engine_id'].nunique())   # 248 engines

# Life span distribution
life_stats = df.groupby('engine_id')['cycle'].max().describe()
print(life_stats)
# count:  248.0
# mean:   ~247 cycles
# min:    ~128 cycles  (shortest lived)
# max:    ~543 cycles  (longest lived)
# → huge variance in engine lifespans under 2 fault modes
```

---

## Section B — RUL & Labels

```python
df['RUL']   = df['max_cycle'] - df['cycle']
df['label'] = (df['RUL'] <= 30).astype(int)
```

**Class distribution for FD004:**
```
label 0 (safe):   ~53,700 rows  (87.6%)
label 1 (danger): ~ 7,500 rows  (12.4%)
→ most imbalanced of all 4 datasets in absolute numbers
```

---

## Section C — Sensor Selection: 19 Useful Sensors (Same as FD002)

Because FD004 has 6 operating conditions (same as FD002), the same set of 19 sensors become useful:

```python
useful_sensors = [s for s in sensor_columns if df[s].nunique() > 2]
print("Useful sensors:", len(useful_sensors))   # 19
```

**FD004 result:**
- **Dropped (2 sensors):** `sensor_16`, `sensor_18` (constant even across all conditions)
- **Kept (19 sensors):** Same 19 as FD002

Even with 2 fault modes, the sensor *set* is the same as FD002 because it's determined by operating conditions (not fault modes). The fault mode affects *how* those sensors change, not *which ones* change.

---

## Section D — Sliding Windows

```python
X, y = make_windows(df, useful_sensors, window_size=30)
print("X shape:", X.shape)   # (54000, 30, 19)
```

**The compounding challenge in a single window:**
```
Engine 47, cycles 210–239 (last 30 before failure):
  Cycle 210: op_condition = [35kft, 0.84 Mach]  → sensor_3 ≈ 0.2 (normalized)
  Cycle 211: op_condition = [0kft, 0.0 Mach]    → sensor_3 ≈ 0.8 (normalized)
  Cycle 212: op_condition = [25kft, 0.62 Mach]  → sensor_3 ≈ 0.5 (normalized)
  ...
  
After normalization, the CNN sees the residual degradation signal:
  "sensor_3 is slightly lower than expected for this condition"
  This residual is what predicts failure — tiny drift within the condition
```

Without normalization, the CNN would see the condition signal (0.2 → 0.8 swings), not the degradation signal (≈0.02 drift per cycle). This is why MinMaxScaler is critical for FD004.

---

## Section F — CNN Architecture

```python
model = FailureCNN(n_sensors=19)
# Same architecture as FD002 model
# in_channels=19 in conv1
```

---

## Section G — Results

**FD004 typical results:**
```
Accuracy:  ~79–84%  (lowest of all 4 datasets)
AUC-ROC:   ~0.88–0.93  (lowest)
Miss Rate: ~15–22%   (highest miss rate)
```

**Why significantly harder:**
- The 30-cycle window may contain 6+ condition transitions
- Degradation signal is buried in condition-variation noise (even after normalization)
- Two failure modes produce different sensor patterns that both need to be learned
- 248 engines = more variety in individual engine behavior (wear rates differ)

**FD004 model in the FL system:**
The FD004 model (Factory Tokyo) tends to be the **weakest performer** in the federated system. However, through FedAvg aggregation with the stronger FD001/FD003 models, it benefits from shared representations — the FL round accuracy for Factory Tokyo typically improves by 3–7% vs training in isolation.

---

## Saved Outputs

```python
with open('scaler_FD004.pkl', 'wb') as f:
    pickle.dump(scaler, f)         # fitted on 61,249 rows × 19 sensors

with open('useful_sensors_FD004.pkl', 'wb') as f:
    pickle.dump(useful_sensors, f)  # 19 sensor names

torch.save(model.state_dict(), 'best_model_FD004.pt')
```

Used by `shap_api.py` when `factory_id=4` (Factory Tokyo).

---

## All 4 Datasets Side-by-Side Summary

| | FD001 | FD002 | FD003 | FD004 |
|--|-------|-------|-------|-------|
| Factory | Mumbai | Berlin | Detroit | Tokyo |
| Train engines | 100 | 260 | 100 | 248 |
| Train rows | 20,631 | 53,759 | 24,720 | 61,249 |
| Windows | ~17,600 | ~46,000 | ~21,500 | ~54,000 |
| Useful sensors | 14 | 19 | 16 | 19 |
| X shape | (17600,30,14) | (46000,30,19) | (21500,30,16) | (54000,30,19) |
| Op conditions | 1 | 6 | 1 | 6 |
| Fault modes | 1 | 1 | 2 | 2 |
| Expected AUC | ~0.97 | ~0.93 | ~0.95 | ~0.90 |
| CNN difficulty | ⭐ Easy | ⭐⭐⭐ Hard | ⭐⭐ Medium | ⭐⭐⭐⭐ Hardest |
