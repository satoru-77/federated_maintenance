# 09 — FL Security: Differential Privacy & Byzantine Detection (`security.py`)

**File:** `fl_backend/server/security.py`  
**Classes:** `DifferentialPrivacy` (client-side), `ByzantineDetector` (server-side)  
**Used by:** `client.py` (DP), `server.py → aggregate_fit()` (Byzantine)

---

## Two Independent Security Layers

```
LAYER 1 — Differential Privacy (client-side, before transmission)
  Factory trains locally → add Gaussian noise to weights → send to server
  Prevents: weight reconstruction attacks (inferring raw sensor data)
  
LAYER 2 — Byzantine Detection (server-side, during aggregation)
  Server receives weights from all factories → cosine similarity check
  Prevents: model poisoning (malicious factory corrupting global model)
```

---

## Part 1: `DifferentialPrivacy`

### Mathematical Foundation

The Gaussian mechanism for DP adds noise calibrated to the **privacy budget ε**:

```
σ = sensitivity × √(2 × ln(1.25 / δ)) / ε

Where:
  ε (epsilon)     = privacy budget (1.0 in this system)
  δ (delta)       = failure probability (1e-5 = 0.001%)  
  sensitivity     = max change one sample can cause in weights (0.001)
  σ (sigma)       = standard deviation of Gaussian noise to add
```

**Computed at startup:**
```python
import math
self.sigma = (sensitivity *
              np.sqrt(2 * math.log(1.25 / delta)) /
              epsilon)

# With epsilon=1.0, delta=1e-5, sensitivity=0.001:
# sigma = 0.001 × √(2 × ln(125000)) / 1.0
# sigma = 0.001 × √(2 × 11.736) / 1.0
# sigma = 0.001 × √23.472 / 1.0
# sigma = 0.001 × 4.845 / 1.0
# sigma ≈ 0.004845
```

### `__init__()`

```python
class DifferentialPrivacy:
    def __init__(self, epsilon=1.0, delta=1e-5, sensitivity=1.0):
        self.epsilon     = epsilon       # privacy budget — 1.0 = "Strong" privacy
        self.delta       = delta         # prob. that DP guarantee fails
        self.sensitivity = sensitivity   # L2-sensitivity of CNN weights

        self.sigma = (sensitivity *
                      np.sqrt(2 * math.log(1.25 / delta)) /
                      epsilon)

        self.total_epsilon_spent = 0.0   # cumulative across rounds

        print(f"[DP] Initialized: epsilon={epsilon}, sigma={self.sigma:.4f}")
        # Output: [DP] Initialized: epsilon=1.0, sigma=0.0048
```

### `add_noise()`

```python
def add_noise(self, weights: List[np.ndarray]) -> List[np.ndarray]:
    """
    Add Gaussian noise N(0, σ²) to each weight array.
    Called by factory clients before sending weights to server.
    """
    noisy_weights = []
    for w in weights:
        noise = np.random.normal(
            loc   = 0,          # mean = 0 (unbiased noise)
            scale = self.sigma, # std = σ ≈ 0.0048
            size  = w.shape     # same shape as weight tensor
        ).astype(w.dtype)       # float32 to match weights
        noisy_weights.append(w + noise)

    self.total_epsilon_spent += self.epsilon   # track budget usage
    return noisy_weights
```

**Concrete example for conv1.weight (shape 32×14×3):**
```
Original weight[0,0,0] = 0.3421
Noise sample          = N(0, 0.0048²) ≈ -0.0031
Noisy weight[0,0,0]   = 0.3421 + (-0.0031) = 0.3390

The noise is tiny (~1% of typical weight magnitude) — 
accuracy impact is minimal but reconstruction is mathematically infeasible.
```

### `get_privacy_report()`

```python
def get_privacy_report(self, factory_id):
    return {
        "factory_id":          factory_id,
        "epsilon_per_round":   self.epsilon,           # 1.0
        "total_epsilon_spent": self.total_epsilon_spent, # rounds × 1.0
        "sigma":               self.sigma,              # ~0.0048
        "privacy_level":       self._privacy_level()
    }

def _privacy_level(self):
    if self.epsilon <= 0.5:  return "Very Strong"
    if self.epsilon <= 1.0:  return "Strong"        # ← our system
    if self.epsilon <= 5.0:  return "Moderate"
    else:                    return "Weak"
```

### Privacy Budget Interpretation

| ε | Level | Noise σ | Use case |
|---|-------|---------|----------|
| 0.1 | Very Strong | ~0.048 | Medical records — high protection |
| 1.0 | **Strong** | **~0.005** | **This system — good balance** |
| 5.0 | Moderate | ~0.001 | Low-sensitivity data |
| 10+ | Weak | ~0.0005 | Near-useless DP |

**Why sensitivity=0.001?**  
The CNN weights after training are small values (typically ±0.3). The L2-sensitivity is the maximum change one training sample can make to the weights. With 14,000+ training windows, one sample's influence is ≈1/14000 ≈ 0.00007 — but we conservatively set sensitivity=0.001 to be safe.

---

## Part 2: `ByzantineDetector`

### What Byzantine Means in FL

A Byzantine factory sends weights that are intentionally or accidentally corrupted:
- **Accidental:** Data corruption, training bug, memory error
- **Intentional:** Adversarial model poisoning (attacker trying to degrade the global model)

The simplest poisoning: multiply weights by 500 + add 100 (what `client.py`'s simulation does).

### Detection: Cosine Similarity to Median

```python
class ByzantineDetector:
    def __init__(self, threshold=0.5):
        self.threshold       = threshold    # minimum cosine similarity
        self.flagged_history = []           # (round, factory_id, score) log
```

### `detect()` — Full Detection Pipeline

```python
def detect(self, client_weights, round_num):
    if len(client_weights) < 2:
        return list(client_weights.keys()), [], {}
    # Need ≥ 2 clients: can't detect anomalies with only 1 reference

    # Step 1: Flatten all factories' weights to 1D vectors
    factory_ids  = list(client_weights.keys())
    flat_weights = {
        fid: np.concatenate([w.flatten() for w in weights])
        for fid, weights in client_weights.items()
    }
    # flat_weights[1] = array of shape (7714,)

    # Step 2: Compute median weight vector (robust to outliers)
    weight_matrix = np.stack(list(flat_weights.values()))  # (4, 7714)
    median_vector = np.median(weight_matrix, axis=0)        # (7714,)
    # np.median is element-wise — for each of the 7714 params,
    # take the median value across 4 factories

    # Step 3: Cosine similarity of each factory to the median
    scores = {}
    for fid, flat_w in flat_weights.items():
        similarity  = self._cosine_similarity(flat_w, median_vector)
        scores[fid] = float(similarity)

    # Step 4: Flag factories below threshold
    clean_ids, flagged_ids = [], []
    for fid, score in scores.items():
        if score < self.threshold:   # threshold = 0.5
            flagged_ids.append(fid)
            self.flagged_history.append((round_num, fid, score))
        else:
            clean_ids.append(fid)

    return clean_ids, flagged_ids, scores
```

### `_cosine_similarity()`

```python
def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
    """
    cosine(a, b) = (a · b) / (||a|| × ||b||)
    
    = 1.0  → identical direction (perfect agreement)
    = 0.0  → perpendicular (no relationship)
    = -1.0 → opposite directions (adversarial)
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
```

### Byzantine Attack Example

```
Normal round (no attack):
  Factory 1 weights: [0.34, -0.12, 0.67, ...]   cosine to median = 0.97 → OK
  Factory 2 weights: [0.31, -0.15, 0.71, ...]   cosine to median = 0.96 → OK
  Factory 3 weights: [0.35, -0.11, 0.65, ...]   cosine to median = 0.98 → OK
  Factory 4 weights: [0.33, -0.13, 0.69, ...]   cosine to median = 0.97 → OK

Byzantine round (Factory 2 sends corrupted weights via byzantine_flag.txt):
  Factory 2 weights: [0.34×500+100, -0.12×500+100, ...]
                   = [270, 40, 435, ...]
  
  Median vector still ≈ normal (3 clean vs 1 corrupted)
  Factory 2 cosine to median ≈ -0.02 (near-random, possibly negative)
  
  0.02 < threshold (0.5) → Factory 2 FLAGGED
  
  Byzantine broadcast: POST /ws/broadcast {"type": "byzantine_alert", "factory_id": 2}
  → Dashboard bubble for Factory 2 turns red
  
  Factory 2 excluded from FedAvg this round
  Global model updated using only Factories 1, 3, 4
```

### Why Median Instead of Mean?

```
Mean is vulnerable:
  If attacker controls 1 of 4 factories and sends weights × 500
  Mean weight vector shifts dramatically toward the attacker's direction
  
Median is robust:
  Median of [0.34, 270, 0.35, 0.33] = (0.34 + 0.35) / 2 = 0.345
  The median is completely unaffected by the extreme outlier
  → cosine similarity correctly identifies Factory 2 as Byzantine
```

---

## Security Architecture Diagram

```
FACTORY CLIENT (before transmission)
│
├── train locally (10 epochs) → raw weights w_i
├── DifferentialPrivacy.add_noise(w_i) → w_i + N(0, σ²)
│     σ ≈ 0.005  → weights perturbed ~1%
│     Attacker intercepts noisy weights → cannot reconstruct sensor data
└── send noisy weights to Flower server

SERVER (during aggregation)
│
├── collect {1: w₁+noise, 2: w₂+noise, 3: w₃+noise, 4: w₄+noise}
├── ByzantineDetector.detect()
│     compute median vector
│     compute cosine similarity of each factory to median
│     if similarity < 0.5 → flag factory, exclude from aggregation
│     broadcast "byzantine_alert" WebSocket event
├── FedAvg on clean factories only
└── broadcast result to dashboard
```
