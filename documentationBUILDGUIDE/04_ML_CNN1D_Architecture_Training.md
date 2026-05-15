# 04 — ML: CNN1D Architecture (`model.py`)

**File:** `fl_backend/client/model.py`  
**Imported by:** `fl_backend/client/client.py`, `machine_learning/notebooks/shap_api.py`  
**Purpose:** The single source of truth for the CNN architecture used across all 4 factory clients and the SHAP API

---

## Design Philosophy

This file contains **only the model architecture** — no training code, no data loading, no evaluation. This clean separation means:
- `client.py` imports it for FL training
- `shap_api.py` imports it for inference
- Both use the exact same `forward()` pass → identical results

---

## Production `FailureCNN` vs Notebook Version

The production model differs from the notebook version in one key place: **pooling strategy**.

| Layer | Notebook (`FailureCNN`) | Production (`FailureCNN`) |
|-------|------------------------|--------------------------|
| After conv1 | `MaxPool1d(kernel_size=2)` → 15 | `ReLU` only, no pool |
| After conv2 | `MaxPool1d(kernel_size=2)` → 7 | `AdaptiveAvgPool1d(1)` → **1** |
| Flatten output | `64 × 7 = 448` | `64 × 1 = 64` |
| FC1 | `Linear(448, 128)` | **Removed** |
| FC output | `Linear(128, 2)` | `Linear(64, 2)` |
| Parameters | ~72,000 | **~7,714** |

**Why `AdaptiveAvgPool1d(1)`?**  
`AdaptiveAvgPool1d(output_size=1)` collapses the entire 30-timestep sequence into a single value per channel — a global average pool. This is sequence-length agnostic (works for any input length) and drastically reduces parameters. The trade-off: loses local temporal resolution. For FL, smaller parameter count means less transmission overhead per round.

---

## Full Class Definition

```python
import torch
import torch.nn as nn


class FailureCNN(nn.Module):
    """
    1D Convolutional Neural Network for turbofan engine failure prediction.

    Input shape:  (batch_size, seq_length, n_sensors)
    Output shape: (batch_size, 2)  → [logit_healthy, logit_failing]

    Trained on NASA CMAPSS dataset.
    Used by all 4 factory clients in the Federated Learning system.
    """

    def __init__(self, n_sensors=14, seq_length=30):
        super(FailureCNN, self).__init__()

        self.n_sensors  = n_sensors
        self.seq_length = seq_length

        # Conv1d: (in_channels, out_channels, kernel_size, padding)
        # in_channels = n_sensors (each sensor = one "channel" in Conv1d terms)
        self.conv1   = nn.Conv1d(in_channels=n_sensors, out_channels=32,
                                  kernel_size=3, padding=1)
        self.conv2   = nn.Conv1d(in_channels=32, out_channels=64,
                                  kernel_size=3, padding=1)
        self.relu    = nn.ReLU()

        # Global average pool: collapses (batch, 64, 30) → (batch, 64, 1)
        self.pool    = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(0.3)

        # Final classifier: 64 features → 2 classes
        self.fc      = nn.Linear(64, 2)

    def forward(self, x):
        # Input:  x shape (batch, seq_length, n_sensors) = (B, 30, 14)
        x = x.permute(0, 2, 1)          # → (B, n_sensors, seq_length) = (B, 14, 30)
        #   Conv1d requires (batch, channels, length)
        #   channels = sensors, length = timesteps

        x = self.relu(self.conv1(x))    # → (B, 32, 30)   padding=1 keeps length
        x = self.relu(self.conv2(x))    # → (B, 64, 30)   padding=1 keeps length

        x = self.pool(x)                # → (B, 64, 1)    global avg over 30 timesteps
        x = x.squeeze(-1)              # → (B, 64)        remove trailing dim

        x = self.dropout(x)             # → (B, 64)        30% zeros during training
        x = self.fc(x)                  # → (B, 2)         logits [healthy, failure]
        return x
```

---

## Tensor Shape Walkthrough (Batch=4, seq=30, sensors=14)

```
Input:          (4, 30, 14)
permute:        (4, 14, 30)     ← swap sensors and timesteps
conv1 + relu:   (4, 32, 30)     ← 32 filters, same length (padding=1)
conv2 + relu:   (4, 64, 30)     ← 64 filters, same length
AdaptiveAvgPool:(4, 64,  1)     ← average pooled across 30 timesteps
squeeze(-1):    (4, 64)         ← flatten last dim
dropout:        (4, 64)         ← 30% zeros (training only, passthrough at eval)
fc:             (4,  2)         ← logits for [HEALTHY, FAILURE]
```

**Converting logits to probabilities:**
```python
probs = torch.softmax(output, dim=1)   # (B, 2)
p_failure = probs[:, 1]                # P(FAILURE) for each window
```

**Converting to binary prediction:**
```python
pred = (p_failure >= 0.5).long()       # 0=HEALTHY, 1=FAILURE
```

---

## Parameter Count Breakdown

```python
model = FailureCNN(n_sensors=14, seq_length=30)
total = sum(p.numel() for p in model.parameters())
print(total)   # 7,714
```

**Per layer:**
```
conv1:   n_sensors × out_channels × kernel + out_channels bias
       = 14 × 32 × 3 + 32 = 1,344 + 32 = 1,376

conv2:   32 × 64 × 3 + 64 = 6,144 + 64 = 6,208

fc:      64 × 2 + 2 = 128 + 2 = 130

Total:   1,376 + 6,208 + 130 = 7,714 parameters
```

**In Federated Learning, these 7,714 parameters are the payload transmitted per factory per round.**  
4 factories × 7,714 params × 4 bytes (float32) = ~123 KB per round. Negligible bandwidth.

---

## Helper Functions

### `get_model()`
```python
def get_model(n_sensors=14, seq_length=30):
    """
    Factory function — returns a fresh untrained model.
    Called by Flower factory clients on startup.
    """
    return FailureCNN(n_sensors=n_sensors, seq_length=seq_length)
```

Usage in `client.py`:
```python
from client.model import get_model
model = get_model(n_sensors=14)
```

### `load_model()`
```python
def load_model(weights_path, n_sensors=14, seq_length=30):
    """
    Load a previously trained model from a .pt file.
    Called by SHAP explainer and evaluation scripts.
    """
    model = FailureCNN(n_sensors=n_sensors, seq_length=seq_length)
    model.load_state_dict(torch.load(weights_path, map_location='cpu'))
    model.eval()
    return model
```

`map_location='cpu'` — loads GPU-trained weights onto CPU. Essential since the SHAP API server and dashboard may not have a GPU.

---

## Self-Test (`__main__` block)

```python
if __name__ == '__main__':
    model       = get_model(n_sensors=14, seq_length=30)
    dummy_input = torch.randn(4, 30, 14)   # batch of 4 windows
    output      = model(dummy_input)

    print(f"Input shape:  {dummy_input.shape}")   # torch.Size([4, 30, 14])
    print(f"Output shape: {output.shape}")        # torch.Size([4, 2])
    status = '✅ PASS' if output.shape == torch.Size([4, 2]) else '❌ FAIL'
    print(f"Status: {status}")
```

Run from `fl_backend/`:
```bash
python -m client.model
```

---

## How the Model Flows Through the System

```
client.py startup:
    model = get_model(n_sensors=14)
    model.load_state_dict(global_weights_from_flower_server)
    ↓
    train locally for 10 epochs (CrossEntropyLoss + Adam)
    ↓
    return model.state_dict() → numpy arrays → sent to Flower server

Flower server (FedAvg):
    receives 4 state_dicts (one per factory)
    averages each parameter tensor weighted by n_samples
    broadcasts averaged weights back to all clients

shap_api.py:
    model = load_model('best_model_FD001.pt', n_sensors=14)
    model.eval()
    x = window_tensor.requires_grad_(True)
    logits = model(x)
    logits[0,1].backward()   # gradient saliency
    saliency = x.grad.abs().mean(dim=1)
```
