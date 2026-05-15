# NB01 — Notebook: FD001 EDA, Preprocessing & CNN Training

**File:** `machine_learning/notebooks/01_fd001.ipynb`  
**Dataset:** NASA CMAPSS FD001 — 100 training engines, 1 operating condition, 1 fault mode (HPC degradation)  
**Purpose:** End-to-end walkthrough: raw CSV → labels → sensor selection → normalization → sliding windows → CNN training → evaluation  
**Output files:** `best_model_FD001.pt`, `scaler_FD001.pkl`, `useful_sensors_FD001.pkl`

---

## Section A — Understanding the Raw Data (Cells 0–3)

### What the raw data looks like

The CMAPSS dataset is a plain text file with no column headers. Each row is one measurement cycle for one engine.

```
Column layout (space-separated):
  engine_id  cycle  op1  op2  op3  s1  s2  s3  s4  s5  s6  s7  s8  s9  s10  s11  s12  s13  s14  s15  s16  s17  s18  s19  s20  s21
```

```python
import pandas as pd

column_names = (
    ['engine_id', 'cycle'] +
    ['op_cond_1', 'op_cond_2', 'op_cond_3'] +
    ['sensor_' + str(i) for i in range(1, 22)]
)

df = pd.read_csv(
    'train_FD001.txt',
    sep='\s+',          # space-separated
    header=None,        # no header row in file
    names=column_names
)

print(df.shape)    # (20631, 26)
print(df.head())
```

**Dataset shape:** 20,631 rows × 26 columns (2 meta + 3 op conditions + 21 sensors).  
Each row = one operating cycle of one engine. Engine 1 has 192 rows (ran for 192 cycles before failing).

---

## Section B — Creating Labels (Cells 20–30)

### Step 1: Compute max cycles per engine

```python
max_cycles = df.groupby('engine_id')['cycle'].max().reset_index()
# Returns: engine_id | cycle (the cycle number at failure)
# e.g. engine_1 ran for 192 cycles total

max_cycles.columns = ['engine_id', 'max_cycle']
df = df.merge(max_cycles, on='engine_id')
# Now every row knows the engine's total lifespan
```

### Step 2: Compute RUL (Remaining Useful Life)

```python
df['RUL'] = df['max_cycle'] - df['cycle']
```

**Intuition:**
```
Engine 1, cycle 1:   max_cycle=192  → RUL = 192 - 1  = 191  (safe)
Engine 1, cycle 100: max_cycle=192  → RUL = 192 - 100 = 92   (safe)
Engine 1, cycle 185: max_cycle=192  → RUL = 192 - 185 = 7    (imminent failure!)
Engine 1, cycle 192: max_cycle=192  → RUL = 192 - 192 = 0    (failed)
```

### Step 3: Create binary label

```python
df['label'] = (df['RUL'] <= 30).astype(int)
# 0 = HEALTHY (more than 30 cycles remaining)
# 1 = FAILURE  (30 cycles or fewer remaining — maintenance window)
```

**Why 30 cycles?** In the CMAPSS literature, 30 cycles is the standard maintenance threshold — enough time to schedule and perform maintenance before actual failure.

**Class distribution for FD001:**
```python
count = df['label'].value_counts()
# label 0 (safe):    ~17,000 rows  (83%)
# label 1 (danger):  ~ 3,600 rows  (17%)
# → significant class imbalance — handled with class_weight in training
```

---

## Section C — Sensor Selection (Cells 31–36)

### Step 4: Identify useless sensors

Some CMAPSS sensors are constant (measure nothing useful under single operating conditions). A constant column contributes zero information to a classifier.

```python
sensor_columns = ['sensor_' + str(i) for i in range(1, 22)]  # 21 sensors

useful_sensors = []
for sensor in sensor_columns:
    if df[sensor].nunique() > 2:         # more than 2 unique values = changing
        useful_sensors.append(sensor)

dropped_sensors = [s for s in sensor_columns if s not in useful_sensors]
print("Dropped (constant):", dropped_sensors)
print("Kept:", len(useful_sensors), "sensors")
```

**FD001 result:**
- **Dropped (7 sensors):** `sensor_1`, `sensor_5`, `sensor_6`, `sensor_10`, `sensor_16`, `sensor_18`, `sensor_19`
- **Kept (14 sensors):** `sensor_2`, `sensor_3`, `sensor_4`, `sensor_7`, `sensor_8`, `sensor_9`, `sensor_11`, `sensor_12`, `sensor_13`, `sensor_14`, `sensor_15`, `sensor_17`, `sensor_20`, `sensor_21`

These 14 sensors form the feature set for the CNN model. The list is saved to `useful_sensors_FD001.pkl`.

### Step 5: Visual validation (Cell 36)

```python
engine_1 = df[df['engine_id'] == 1].copy()
failure_cycle = engine_1['cycle'].max()   # 192
danger_start  = failure_cycle - 30        # 162

fig, axes = plt.subplots(3, 2, figsize=(14, 10))
for i, (ax, sensor) in enumerate(zip(axes.flat, useful_sensors[:6])):
    ax.plot(engine_1['cycle'], engine_1[sensor])
    ax.axvline(x=danger_start, color='red', linestyle='--', label='Danger zone starts')
    ax.set_title(sensor)
```

Purpose: visually confirm that useful sensors show a visible trend or change near the failure zone.

---

## Section D — Normalization (Cells 37–41)

### Step 6: MinMax scaling

```python
from sklearn.preprocessing import MinMaxScaler

scaler = MinMaxScaler()
# Formula: (x - min) / (max - min) → maps to [0, 1]

df[useful_sensors] = scaler.fit_transform(df[useful_sensors])
# fit_transform on training data only — scaler learns min/max from train set

# Save scaler for use in SHAP API and inference
import pickle
with open('scaler_FD001.pkl', 'wb') as f:
    pickle.dump(scaler, f)
```

**Why normalize?**
- `sensor_3` has values in range [1400, 1650] (temperature in Rankine)
- `sensor_15` has values in range [8.3, 8.5] (bleed enthalpy)
- Without normalization, `sensor_3` dominates the CNN's weight updates by orders of magnitude

---

## Section E — Sliding Windows (Cells 42–46)

### Step 7: `make_windows()` function

This is the core preprocessing step that converts the time-series table into 3D tensors for the CNN.

```python
import numpy as np

def make_windows(dataframe, sensor_cols, window_size=30):
    """
    Creates 30-cycle sliding windows across each engine's sensor readings.
    
    Args:
        dataframe:   full DataFrame with sensor columns and 'engine_id', 'label'
        sensor_cols: list of sensor column names to use as features
        window_size: number of consecutive cycles per window (default: 30)
    
    Returns:
        X: numpy array of shape (N_windows, window_size, n_sensors)
        y: numpy array of shape (N_windows,) — label of last row in window
    """
    X, y = [], []
    
    for engine_id in dataframe['engine_id'].unique():
        edf = dataframe[dataframe['engine_id'] == engine_id].sort_values('cycle')
        sensors = edf[sensor_cols].values   # shape: (n_cycles, n_sensors)
        labels  = edf['label'].values       # shape: (n_cycles,)
        
        # Slide a 30-cycle window across the engine's full history
        for start in range(len(edf) - window_size + 1):
            end = start + window_size
            X.append(sensors[start:end])    # 30 rows × 14 sensors
            y.append(labels[end - 1])       # label of the LAST row in window
    
    return np.array(X), np.array(y)

X, y = make_windows(df, useful_sensors, window_size=30)
print("X shape:", X.shape)    # (N, 30, 14)
print("y shape:", y.shape)    # (N,)
# For FD001: X shape ≈ (17,631, 30, 14)
```

**Why label the last row?**  
The window's label represents what the sensor pattern is *leading to*. If cycles 161–190 of a 192-cycle engine are in the window, the last row (cycle 190) has RUL=2 → label=1 (FAILURE). The CNN learns that this 30-cycle pattern is a failure precursor.

**Window pseudocode for engine_1 (192 cycles):**
```
Window 1:  cycles 1–30   → label = label at cycle 30  (RUL=162 → 0 HEALTHY)
Window 2:  cycles 2–31   → label = label at cycle 31  (RUL=161 → 0 HEALTHY)
...
Window 163: cycles 163–192 → label = label at cycle 192 (RUL=0 → 1 FAILURE)
Total windows for engine_1 = 192 - 30 + 1 = 163 windows
```

---

## Section F — Train/Val Split & Model (Cells 47–59)

### Step 8: Split data

```python
from sklearn.model_selection import train_test_split

X_train, X_val, y_train, y_val = train_test_split(
    X, y,
    test_size=0.2,       # 80% train, 20% validation
    random_state=42,
    stratify=y           # ensures same failure/safe ratio in both splits
)
print("Train:", X_train.shape)    # ≈ (14,104, 30, 14)
print("Val:",   X_val.shape)      # ≈ (3,527,  30, 14)
```

### Step 9: CNN Architecture

```python
import torch
import torch.nn as nn

class FailureCNN(nn.Module):
    def __init__(self, n_sensors, seq_length=30):
        super(FailureCNN, self).__init__()
        
        # Conv layer 1: 32 filters, kernel_size=3
        # Each filter looks at 3 consecutive cycles
        self.conv1 = nn.Conv1d(
            in_channels=n_sensors,   # 14 input channels (one per sensor)
            out_channels=32,         # 32 learned patterns
            kernel_size=3,
            padding=1                # same padding: output same length as input
        )
        self.bn1   = nn.BatchNorm1d(32)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool1d(kernel_size=2)   # halves length: 30 → 15
        
        # Conv layer 2: 64 filters, kernel_size=3
        self.conv2 = nn.Conv1d(32, 64, kernel_size=3, padding=1)
        self.bn2   = nn.BatchNorm1d(64)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool1d(kernel_size=2)   # halves length: 15 → 7
        
        # Flatten and classify
        self.flatten = nn.Flatten()
        # After pool2: 64 channels × 7 timesteps = 448 features
        self.fc1     = nn.Linear(64 * 7, 128)
        self.dropout = nn.Dropout(0.3)             # prevents overfitting
        self.fc2     = nn.Linear(128, 2)           # 2 output classes: HEALTHY, FAILURE
    
    def forward(self, x):
        # x input shape: (batch, seq_len, n_sensors) = (B, 30, 14)
        x = x.permute(0, 2, 1)   # → (B, 14, 30): Conv1d expects (batch, channels, length)
        
        x = self.pool1(self.relu1(self.bn1(self.conv1(x))))  # → (B, 32, 15)
        x = self.pool2(self.relu2(self.bn2(self.conv2(x))))  # → (B, 64, 7)
        x = self.flatten(x)                                   # → (B, 448)
        x = self.dropout(torch.relu(self.fc1(x)))             # → (B, 128)
        x = self.fc2(x)                                       # → (B, 2)
        return x

model = FailureCNN(n_sensors=len(useful_sensors))
# Total parameters: ~72,000 (deliberately kept small for fast FL training)
```

**Key design choices:**
- `Conv1d` (1D convolution) because the data is 1D time series (not images)
- `permute(0,2,1)` required because PyTorch Conv1d expects `(batch, channels, length)` not `(batch, length, channels)`
- 2 MaxPool layers → sequence compressed from 30 to 7 timesteps
- `Dropout(0.3)` — randomly zeros 30% of neurons during training to prevent memorization

### Step 10: Training Loop

```python
from sklearn.metrics import roc_auc_score

device   = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model    = model.to(device)

# Class weights: inverse of class frequency — gives more weight to rare FAILURE samples
class_counts  = np.bincount(y_train)        # [n_healthy, n_failure]
class_weights = 1.0 / class_counts          # [1/n_healthy, 1/n_failure]
class_weights = torch.FloatTensor(class_weights).to(device)

criterion = nn.CrossEntropyLoss(weight=class_weights)
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

# Convert to tensors
X_train_t = torch.FloatTensor(X_train).to(device)
y_train_t = torch.LongTensor(y_train).to(device)
X_val_t   = torch.FloatTensor(X_val).to(device)

EPOCHS   = 50
best_auc = 0.0

for epoch in range(EPOCHS):
    # ── Training phase ──
    model.train()
    optimizer.zero_grad()
    outputs = model(X_train_t)                          # forward pass
    loss    = criterion(outputs, y_train_t)             # compute loss
    loss.backward()                                     # backprop
    optimizer.step()                                    # update weights
    
    # ── Validation phase ──
    model.eval()
    with torch.no_grad():
        val_out = model(X_val_t)
        probs   = torch.softmax(val_out, dim=1)[:, 1].cpu().numpy()  # P(FAILURE)
    
    auc = roc_auc_score(y_val, probs)
    acc = (np.round(probs) == y_val).mean()
    
    # Save best model by AUC (not accuracy — AUC handles imbalance better)
    if auc > best_auc:
        best_auc   = auc
        best_epoch = epoch
        torch.save(model.state_dict(), 'best_model_FD001.pt')
    
    if epoch % 5 == 0:
        print(f"Epoch {epoch:3d}  Loss: {loss:.4f}  Acc: {acc:.3f}  AUC: {auc:.4f}")
```

**Why AUC-ROC for model selection (not accuracy)?**  
With 83% healthy samples, a model that always predicts HEALTHY gets 83% accuracy but 0.5 AUC. AUC measures the model's ability to rank failure samples above healthy ones — immune to class imbalance.

**Class weighting formula:**
```
n_healthy = 17,000   → weight = 1/17000 = 0.000059
n_failure =  3,600   → weight = 1/3600  = 0.000278
ratio = 0.000278 / 0.000059 ≈ 4.7×
→ each FAILURE sample contributes 4.7× more to the loss than a HEALTHY sample
```

---

## Section G — Evaluation (Cells 60–68)

### Confusion Matrix

```python
from sklearn.metrics import confusion_matrix

cm = confusion_matrix(y_val, preds)   # preds = (probs >= 0.5).astype(int)
tn, fp, fn, tp = cm.ravel()

print("True Negatives  (correctly said SAFE):   ", tn)
print("False Positives (wrongly said DANGER):   ", fp, "← false alarm")
print("False Negatives (missed real failures):  ", fn, "← CRITICAL miss")
print("True Positives  (correctly said DANGER): ", tp)
print()
print("Miss Rate:", fn / (fn + tp))    # how often real failures are missed
print("False Alarm Rate:", fp / (fp + tn))
```

**FD001 typical results:**
```
Accuracy:  ~88–92%
AUC-ROC:   ~0.95–0.98
Miss Rate: ~5–12%  (missing 1 in 10 real failures)
```

### ROC Curve (Cell 66)

```python
from sklearn.metrics import roc_curve, auc

fpr, tpr, thresholds = roc_curve(y_val, probs)
roc_auc = auc(fpr, tpr)

plt.plot(fpr, tpr, color='steelblue', label=f'AUC = {roc_auc:.3f}')
plt.plot([0,1],[0,1], 'k--')   # random baseline
plt.xlabel('False Positive Rate (False Alarms)')
plt.ylabel('True Positive Rate (Failures Caught)')
plt.title('ROC Curve — FD001')
```

---

## Saved Outputs

| File | Contents | Used by |
|------|---------|---------|
| `best_model_FD001.pt` | CNN state dict at best AUC epoch | `shap_api.py` model loading |
| `scaler_FD001.pkl` | Fitted MinMaxScaler (min/max per sensor) | `shap_api.py` inference preprocessing |
| `useful_sensors_FD001.pkl` | List of 14 sensor column names | `shap_api.py` column selection |

```python
import pickle

with open('scaler_FD001.pkl', 'wb') as f:
    pickle.dump(scaler, f)

with open('useful_sensors_FD001.pkl', 'wb') as f:
    pickle.dump(useful_sensors, f)

torch.save(model.state_dict(), 'best_model_FD001.pt')
```

---

## Full Pipeline Summary

```
train_FD001.txt  (20,631 rows × 26 cols)
    ↓
Add RUL column → df['RUL'] = max_cycle - cycle
    ↓
Add label → df['label'] = (RUL <= 30).astype(int)
    ↓
Drop 7 constant sensors → 14 useful sensors remain
    ↓
MinMaxScaler.fit_transform() → all values in [0, 1]
    ↓
make_windows(window_size=30) → X shape: (17631, 30, 14)
    ↓
train_test_split(stratify=y, test_size=0.2)
    ↓
FailureCNN(n_sensors=14) → 2×Conv1D + MaxPool + FC
    ↓
Train 50 epochs, CrossEntropyLoss(weighted), Adam lr=0.001
Save best model by AUC-ROC on val set
    ↓
Output: best_model_FD001.pt, scaler_FD001.pkl, useful_sensors_FD001.pkl
```
