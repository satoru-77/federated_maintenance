# 03 — ML: CMAPSS Dataset Preprocessing (`data_loader.py`)

**File:** `fl_backend/client/data_loader.py`  
**Called by:** `fl_backend/client/client.py` → `load_factory_data(factory_id)`  
**Purpose:** Load, label, normalize, and window-ify each factory's CMAPSS dataset for FL training

---

## Critical Design Decision: Fixed Sensor Set

The production `data_loader.py` diverges from the notebooks in one important way:

**Notebooks** used per-factory sensor selection (14/19/16/19 sensors per factory).  
**Production FL** uses a **fixed 14-sensor list** across all 4 factories.

```python
FIXED_SENSORS = [
    'sensor_2',  'sensor_3',  'sensor_4',  'sensor_7',
    'sensor_8',  'sensor_9',  'sensor_11', 'sensor_12',
    'sensor_13', 'sensor_14', 'sensor_15', 'sensor_17',
    'sensor_20', 'sensor_21'
]
```

**Why?** Federated Learning requires all factory clients to share the **same model architecture**. The model has a fixed `in_channels` equal to `n_sensors`. If Factory 1 uses 14 sensors and Factory 2 uses 19, their `Conv1d(in_channels=14)` and `Conv1d(in_channels=19)` would produce **incompatible weight tensors** — FedAvg cannot average them.

Solution: use the 14 sensors common to all datasets (FD001's useful set, which is a strict subset of FD002/FD003/FD004's useful sets).

---

## Factory → Dataset Mapping

```python
FACTORY_DATASETS = {
    1: 'train_FD001.txt',   # Mumbai  — 100 engines
    2: 'train_FD002.txt',   # Berlin  — 260 engines (truncated to 100 in FL)
    3: 'train_FD003.txt',   # Detroit — 100 engines
    4: 'train_FD004.txt',   # Tokyo   — 248 engines (truncated to 100 in FL)
}

FACTORY_N_SENSORS = {
    1: 14,   # used in get_model() calls — all factories → 14
    2: 19,
    3: 16,
    4: 19,
}
# Note: FACTORY_N_SENSORS reflects notebook findings but is NOT used
# by the production loader — FIXED_SENSORS overrides it.
```

---

## `load_factory_data()` — Full Walkthrough

```python
def load_factory_data(factory_id, data_dir='.', window_size=30):
    filename = os.path.join(data_dir, FACTORY_DATASETS[factory_id])
```

### Step 1: Load Raw CSV

```python
col_names = (
    ['engine_id', 'cycle'] +
    ['setting_1', 'setting_2', 'setting_3'] +
    ['sensor_' + str(i) for i in range(1, 22)]
)
df = pd.read_csv(filename, sep=r'\s+', header=None)
df.columns = col_names
```

### Step 2: Memory Cap for FD002 and FD004

```python
if factory_id in [2, 4]:
    max_engine = 100
    df = df[df.iloc[:, 0] <= max_engine]   # keep engines 1–100 only
    print(f"Factory {factory_id}: using first {max_engine} engines (memory limit)")
```

**Why 100 engines cap?**  
FD002 has 260 engines (53,759 rows), FD004 has 248 engines (61,249 rows). Training on all of them in a Flower client would use significant RAM and slow each FL round. Capping to 100 engines still preserves the **Non-IID characteristic** (6 operating conditions) while keeping memory under ~2 GB per process.

**Impact on dataset sizes in production FL:**
```
Factory 1: 100 engines → ~17,700 windows  (unchanged)
Factory 2: 100 engines → ~17,600 windows  (was ~46,000 in notebooks)
Factory 3: 100 engines → ~21,500 windows  (unchanged)
Factory 4: 100 engines → ~17,600 windows  (was ~54,000 in notebooks)
```

### Step 3: RUL and Labels

```python
max_cycles = df.groupby('engine_id')['cycle'].max().reset_index()
max_cycles.columns = ['engine_id', 'max_cycle']
df = df.merge(max_cycles, on='engine_id')
df['RUL']   = df['max_cycle'] - df['cycle']
df['label'] = (df['RUL'] <= 30).astype(int)
# 1 = FAILURE (≤ 30 cycles remaining), 0 = HEALTHY
```

### Step 4: Normalize with MinMaxScaler

```python
scaler = MinMaxScaler()
df[useful_sensors] = scaler.fit_transform(df[useful_sensors])
df[useful_sensors] = df[useful_sensors].astype(np.float32)
# float32 instead of float64 — halves memory, no precision loss for CNN
```

**Each factory fits its own scaler on its own data.** This means Factory 1's scaler learns min/max from FD001 values only; Factory 2's scaler learns from FD002 values only. No cross-factory normalization. This is correct — each factory maintains data privacy.

### Step 5: Create Sliding Windows

```python
X, y = _make_windows(df, useful_sensors, window_size)
```

See `_make_windows()` below.

### Step 6: Train/Validation Split

```python
X_train, X_val, y_train, y_val = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y        # preserves failure/healthy ratio in both splits
)
return X_train, X_val, y_train, y_val, scaler, useful_sensors
```

---

## `_make_windows()` — Internal Window Generator

```python
def _make_windows(df, sensor_cols, window_size):
    """Internal — creates sliding windows from dataframe."""
    X, y = [], []
    
    for eid in df['engine_id'].unique():
        edf    = df[df['engine_id'] == eid].sort_values('cycle')
        vals   = edf[sensor_cols].values           # (n_cycles, n_sensors) float32
        labels = edf['label'].values               # (n_cycles,)
        
        for i in range(len(edf) - window_size + 1):
            X.append(vals[i : i + window_size])    # (30, 14)
            y.append(labels[i + window_size - 1])  # label of last row
    
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int64)
```

**Output shapes per factory (production — 100-engine cap):**
```
Factory 1: X=(~14,160, 30, 14)  y=(~14,160,)
Factory 2: X=(~14,080, 30, 14)  y=(~14,080,)
Factory 3: X=(~17,234, 30, 14)  y=(~17,234,)
Factory 4: X=(~14,080, 30, 14)  y=(~14,080,)
```

---

## Difference: Notebook vs Production

| Aspect | Notebooks (01–04) | Production (data_loader.py) |
|--------|------------------|-----------------------------|
| Sensor count | Per-factory (14/19/16/19) | Fixed 14 (all factories) |
| FD002 engines | All 260 | First 100 only |
| FD004 engines | All 248 | First 100 only |
| dtype | float64 | float32 (memory optimized) |
| Scaler saved | Yes (pkl) | No (in-memory only) |
| Purpose | Research/exploration | FL training production |

---

## Quick Test (`__main__` block)

```python
if __name__ == '__main__':
    for fid in [1, 2, 3, 4]:
        X_tr, X_val, y_tr, y_val, scaler, sensors = load_factory_data(fid, data_dir='.')
        print(f"  Factory {fid}: X_train={X_tr.shape}, "
              f"sensors={len(sensors)}, "
              f"failure_rate={y_tr.mean():.1%}")
```

Run from `fl_backend/` with:
```bash
python -m client.data_loader
```

Expected output:
```
Factory 1: X_train=(14160, 30, 14), sensors=14, failure_rate=16.8%
Factory 2: X_train=(14080, 30, 14), sensors=14, failure_rate=15.2%
Factory 3: X_train=(17234, 30, 14), sensors=14, failure_rate=12.4%
Factory 4: X_train=(14080, 30, 14), sensors=14, failure_rate=13.1%
```
