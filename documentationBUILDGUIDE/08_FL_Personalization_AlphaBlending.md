# 08 — FL Personalization: Alpha Blending (`personalization.py`)

**File:** `fl_backend/server/personalization.py`  
**Called by:** `server.py → _run_personalization()` after clustering stabilises  
**Key functions:** `blend_weights()`, `evaluate_weights()`, `grid_search_alpha()`, `PersonalizationManager`

---

## What Personalization Solves

After clustering, each factory receives **cluster-averaged weights** — a better fit than global FedAvg, but still a compromise between the 2 factories in the cluster. Personalization finds the optimal mix of:
- **Cluster weights**: shared knowledge from the cluster group
- **Local weights**: specialized knowledge from this factory's own data

```
final_weights = α × cluster_weights + (1 - α) × local_weights

α = 1.0: use cluster weights entirely (ignore local specialization)
α = 0.0: use local weights entirely (ignore cluster collaboration)
α = 0.7: 70% cluster + 30% local  (common best for FD001/FD003)
α = 0.5: equal blend               (common best for FD002/FD004)
```

---

## `blend_weights()` — Layer-wise Interpolation

```python
def blend_weights(cluster_weights, local_weights, alpha):
    """
    Blend cluster model and local model weights.
    formula: blended[l] = α * cluster[l] + (1-α) * local[l]
    
    Applied independently to every layer:
      conv1.weight, conv1.bias, conv2.weight, conv2.bias, fc.weight, fc.bias
    """
    blended = []
    for cw, lw in zip(cluster_weights, local_weights):
        blended.append(alpha * cw + (1 - alpha) * lw)
    return blended
```

**Concrete example for conv1.weight (shape: 32×14×3 = 1,344 values):**
```
cluster_weights[0][0,0,0] = 0.3421   (cluster's learned filter)
local_weights[0][0,0,0]   = 0.5812   (factory's local filter)

α = 0.7:
blended[0][0,0,0] = 0.7 × 0.3421 + 0.3 × 0.5812
                   = 0.2395 + 0.1744
                   = 0.4139
```

This is applied element-wise across all 7,714 parameters simultaneously.

---

## `evaluate_weights()` — Load & Score

```python
def evaluate_weights(model, weights, X_val, y_val):
    """
    Load weights into model and evaluate on validation data.
    Returns accuracy.  threshold=0.4 (consistent with client.py)
    """
    # Load the weight list into the model's state_dict
    params_dict = zip(model.state_dict().keys(), weights)
    state_dict  = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
    model.load_state_dict(state_dict, strict=True)
    model.eval()

    X_tensor = torch.FloatTensor(X_val)
    with torch.no_grad():
        outputs = model(X_tensor)
        probs   = torch.softmax(outputs, dim=1)[:, 1].numpy()
        preds   = (probs > 0.4).astype(int)    # 0.4 threshold (same as client.py)
    
    return float((preds == y_val).mean())
```

---

## `grid_search_alpha()` — The Core Search

```python
def grid_search_alpha(factory_id, cluster_weights, local_weights,
                      model, X_val, y_val, alpha_values=None):
    if alpha_values is None:
        alpha_values = [round(a * 0.1, 1) for a in range(1, 10)]
        # [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        # Note: 0.0 and 1.0 are excluded (pure local or pure cluster)

    # Use at most 2,000 validation samples for speed
    max_samples = min(len(X_val), 2000)
    X_val = X_val[:max_samples]
    y_val = y_val[:max_samples]

    best_alpha    = 0.5
    best_accuracy = 0.0
    all_results   = {}

    for alpha in alpha_values:   # 9 iterations
        blended  = blend_weights(cluster_weights, local_weights, alpha)
        accuracy = evaluate_weights(model, blended, X_val, y_val)
        all_results[alpha] = accuracy

        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_alpha    = alpha

    # Save best alpha to factories table
    update_factory_alpha(factory_id, best_alpha)
    # → UPDATE factories SET alpha_value=best_alpha WHERE factory_id=factory_id

    return best_alpha, best_accuracy, all_results
```

**Printed output during grid search:**
```
[Personalization] Factory 1 — grid search alpha
  α=0.1 → accuracy=0.7823
  α=0.2 → accuracy=0.8012
  α=0.3 → accuracy=0.8156
  α=0.4 → accuracy=0.8201
  α=0.5 → accuracy=0.8134
  α=0.6 → accuracy=0.8198
  α=0.7 → accuracy=0.8321   ← best
  α=0.8 → accuracy=0.8245
  α=0.9 → accuracy=0.8102
  Best: α=0.7 → accuracy=0.8321
```

**Why Factory 1 prefers high α (0.7)?**
Factory 1 (FD001, 1 condition) benefits more from cluster knowledge because its cluster partner (Factory 3, FD003) has a similar but complementary fault mode (2 faults vs 1). The cluster model has seen both HPC and fan degradation patterns → richer representation → α=0.7 favors the cluster.

**Why Factory 2 prefers lower α (0.5)?**
Factory 2 (FD002, 6 conditions) and its cluster partner (Factory 4, FD004) both struggle with multi-condition complexity. Their cluster model is only marginally better than either's local model → equal blend (α=0.5) is optimal.

---

## `PersonalizationManager` — Orchestrator

```python
class PersonalizationManager:
    def __init__(self):
        self.best_alphas     = {}   # {factory_id: best_alpha}
        self.best_accuracies = {}   # {factory_id: best_accuracy}
        self.has_run         = False  # prevents running twice

    def run_personalization(self, factory_id, cluster_weights,
                            local_weights, model, X_val, y_val):
        best_alpha, best_acc, results = grid_search_alpha(
            factory_id, cluster_weights, local_weights, model, X_val, y_val
        )
        self.best_alphas[factory_id]     = best_alpha
        self.best_accuracies[factory_id] = best_acc
        return best_alpha, best_acc

    def get_summary(self):
        print("\n[Personalization] === SUMMARY ===")
        for fid in sorted(self.best_alphas.keys()):
            print(f"  Factory {fid}: "
                  f"best α={self.best_alphas[fid]:.1f}, "
                  f"accuracy={self.best_accuracies[fid]:.4f}")
```

---

## How It Fits Into the Server Loop

`_run_personalization()` in `server.py` calls this for each factory in sequence:

```python
# server.py._run_personalization():
for factory_id, local_weights in self.latest_client_weights.items():
    cluster_id      = self.clustering.current_clusters.get(factory_id)
    cluster_weights = self.cluster_manager.get_cluster_weights(cluster_id)

    # Load factory's validation data fresh
    _, X_val, _, y_val, _, _ = load_factory_data(factory_id, data_dir='./client')

    model = FailureCNN(n_sensors=14, seq_length=30)

    self.personalization.run_personalization(
        factory_id, cluster_weights, local_weights, model, X_val, y_val
    )

    # Memory cleanup after each factory — inside the loop
    del model, X_val, y_val
    import gc; gc.collect()
    # Critical: personalization loads 4 factories' validation data
    # Without gc.collect(), memory usage spikes to ~8GB
```

---

## Complete Personalization Pipeline

```
After clustering fires (round 10+):

For each factory i:
  cluster_weights  = cluster_manager.get_cluster_weights(cluster_id_i)
  local_weights    = latest_client_weights[i]  (from most recent fit() call)
  X_val, y_val     = load_factory_data(i)       (re-load for eval)

  Grid search:
    FOR α in [0.1, 0.2, ..., 0.9]:
      blended = α × cluster_weights + (1-α) × local_weights
      accuracy = eval(blended, X_val, y_val)
    
    best_α = argmax accuracy over all α

  Update DB:
    UPDATE factories SET alpha_value=best_α WHERE factory_id=i

Summary (typical results):
  Factory 1 (FD001): best α=0.7, accuracy=0.8321
  Factory 2 (FD002): best α=0.5, accuracy=0.7204
  Factory 3 (FD003): best α=0.8, accuracy=0.8512
  Factory 4 (FD004): best α=0.6, accuracy=0.7098
```
