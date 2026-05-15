# NB02 — Notebook: FD002 EDA, Preprocessing & CNN Training

**File:** `machine_learning/notebooks/02_fd002.ipynb`  
**Dataset:** NASA CMAPSS FD002 — 260 training engines, **6 operating conditions**, 1 fault mode (HPC degradation)  
**Key difference from FD001:** Multiple operating conditions cause sensor readings to shift dramatically between cycles — makes the CNN task significantly harder.  
**Output files:** `best_model_FD002.pt`, `scaler_FD002.pkl`, `useful_sensors_FD002.pkl`

---

> **Structure note:** FD002 follows the same 7-section pipeline as FD001 (NB01). This doc focuses on what is **different** in FD002 rather than repeating the shared logic. Refer to NB01 for the base pipeline.

---

## What Makes FD002 Different: 6 Operating Conditions

FD001 engines all run under the same conditions (altitude, throttle, speed). FD002 engines cycle through **6 distinct operating regimes** within a single flight cycle.

```
Operating conditions in FD002:
  op_cond_1: altitude          (e.g., 0, 10, 20, 25, 35, 42 kft)
  op_cond_2: Mach number       (e.g., 0.0, 0.2, 0.42, 0.62, 0.84)
  op_cond_3: throttle resolver angle (TRA)

Effect on sensors:
  At altitude 0   → sensor_3 ≈ 1500  (sea-level temperature)
  At altitude 35  → sensor_3 ≈ 1400  (thinner air, cooler)
  → same engine, same health, but sensor reads 100 units different
```

This is the **Non-IID problem** in practice: raw sensor values cannot be compared across operating conditions without normalization.

---

## Dataset Statistics vs FD001

| Property | FD001 | FD002 |
|----------|-------|-------|
| Training engines | 100 | 260 |
| Test engines | 100 | 259 |
| Operating conditions | 1 | 6 |
| Fault modes | 1 | 1 |
| Total rows (train) | 20,631 | 53,759 |
| Total windows | ~17,600 | ~46,800 |
| Useful sensors | 14 | 19 |
| Avg engine life | ~206 cycles | ~206 cycles |

---

## Section A — Data Loading (Same as FD001, different file)

```python
column_names = (
    ['engine_id', 'cycle'] +
    ['op_cond_1', 'op_cond_2', 'op_cond_3'] +
    ['sensor_' + str(i) for i in range(1, 22)]
)

df = pd.read_csv('train_FD002.txt', sep='\s+', header=None, names=column_names)
print(df.shape)   # (53759, 26)
```

---

## Section B — RUL & Labels (Identical logic)

```python
max_cycles = df.groupby('engine_id')['cycle'].max().reset_index()
max_cycles.columns = ['engine_id', 'max_cycle']
df = df.merge(max_cycles, on='engine_id')
df['RUL']   = df['max_cycle'] - df['cycle']
df['label'] = (df['RUL'] <= 30).astype(int)
```

**Class distribution for FD002:**
```
label 0 (safe):   ~45,700 rows  (85%)
label 1 (danger): ~ 8,000 rows  (15%)
→ even more imbalanced than FD001 (more engines, similar proportional failure zone)
```

---

## Section C — Sensor Selection: More Sensors Useful

Because FD002 has 6 operating conditions, sensors that were constant in FD001 (single condition) now **vary** as the engine transitions between conditions. This means more sensors pass the `nunique() > 2` filter.

```python
useful_sensors = []
for sensor in sensor_columns:
    if df[sensor].nunique() > 2:
        useful_sensors.append(sensor)

print("Useful sensors:", len(useful_sensors))   # 19
print(useful_sensors)
```

**FD002 result:**
- **Dropped (2 sensors):** `sensor_16`, `sensor_18` (still constant even across 6 conditions)
- **Kept (19 sensors):** sensors 1–15, 17, 19, 20, 21 — 5 more than FD001
  - Sensors newly useful in FD002: `sensor_1`, `sensor_5`, `sensor_6`, `sensor_10`, `sensor_19`

**Why the difference?**
- `sensor_1` (Fan inlet total temperature) is constant at sea level (FD001) but varies with altitude (FD002)
- `sensor_5` (Physical fan speed) changes with throttle across different conditions
- The multi-condition environment makes more physical quantities relevant

---

## Section D — Normalization: Critical for Multi-Condition Data

In FD001, MinMaxScaler simply compressed the single operating point's range. In FD002, normalization is **essential for correctness** — without it, the model sees the operating condition signal rather than the degradation signal.

```python
from sklearn.preprocessing import MinMaxScaler

scaler = MinMaxScaler()
df[useful_sensors] = scaler.fit_transform(df[useful_sensors])

# After normalization:
# sensor_3 at sea level (1500) → 1.0
# sensor_3 at altitude 35 (1400) → 0.0
# sensor_3 degraded at sea level (1485) → ~0.85
# The model now sees relative degradation, not absolute operating condition
```

---

## Section E — Sliding Windows

`make_windows()` is identical to FD001. With 260 engines averaging ~206 cycles each:

```
Windows per engine ≈ 206 - 30 + 1 = 177 windows
Total windows ≈ 260 × 177 ≈ 46,020 windows

X shape: (46020, 30, 19)   ← 19 features instead of 14
y shape: (46020,)
```

---

## Section F — CNN Architecture: Wider Input Layer

The architecture is identical to FD001's `FailureCNN` **except** `n_sensors=19`:

```python
model = FailureCNN(n_sensors=19)
# n_sensors=19 changes: in_channels in conv1 = 19 (not 14)
# Everything else identical: 32→64 filters, MaxPool×2, FC(448→128→2)

# Total parameters: slightly more than FD001 (~75,000 vs ~72,000)
# The extra 5 sensors add 5 × 32 = 160 parameters to conv1
```

**Input tensor shape:** `(batch, 30, 19)` → after `permute(0,2,1)` → `(batch, 19, 30)`

---

## Section G — Training

Identical training loop. Key numbers for FD002:

```python
EPOCHS = 50
# Class weights still computed:
class_counts  = np.bincount(y_train)
class_weights = 1.0 / class_counts
# → FAILURE samples get ~5.7× more weight than HEALTHY

criterion = nn.CrossEntropyLoss(weight=class_weights_tensor)
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
```

**FD002 typical results:**
```
Accuracy:  ~82–87%  (lower than FD001 — harder due to 6 conditions)
AUC-ROC:   ~0.91–0.95  (lower than FD001's ~0.97)
Miss Rate: ~10–18%  (higher miss rate — multi-condition harder to learn)
```

**Why harder than FD001?**
- The CNN must learn to distinguish degradation patterns *within* each operating condition
- With 6 condition transitions per cycle, the 30-cycle window may contain mixed conditions
- The model must implicitly learn to normalize for operating point internally

---

## Saved Outputs

```python
with open('scaler_FD002.pkl', 'wb') as f:
    pickle.dump(scaler, f)          # MinMaxScaler fitted on 53,759 rows

with open('useful_sensors_FD002.pkl', 'wb') as f:
    pickle.dump(useful_sensors, f)  # 19 sensor names

torch.save(model.state_dict(), 'best_model_FD002.pt')
```

These files are **used by shap_api.py** when `factory_id=2` (Factory Berlin). The SHAP API loads `scaler_FD002.pkl` and `useful_sensors_FD002.pkl` to preprocess the test data identically to training.

---

## FD002 vs FD001 Side-by-Side Pipeline

```
                    FD001                    FD002
Raw rows:           20,631                   53,759
Useful sensors:     14                       19
Window count:       ~17,600                  ~46,000
X shape:            (17600, 30, 14)          (46000, 30, 19)
CNN in_channels:    14                       19
Expected AUC:       ~0.97                    ~0.93
Difficulty:         Easier                   Harder
```
