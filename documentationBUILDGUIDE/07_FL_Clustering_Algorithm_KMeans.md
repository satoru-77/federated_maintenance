# 07 — FL Clustering: K-Means on Weight Gradients (`clustering.py`)

**File:** `fl_backend/server/clustering.py`  
**Class:** `AdaptiveClustering`  
**Called by:** `server.py → _trigger_clustering()` at round 10 or accuracy plateau  
**Depends on:** `sklearn.cluster.KMeans`, `sklearn.metrics.silhouette_score`, `db_logger.log_cluster_assignment`

---

## Core Insight: What Is a "Gradient" Here?

In standard ML, a gradient is `∂Loss/∂weights` (backprop). Here it means something different:

```
gradient_i = global_weights_flat - factory_i_weights_flat

"How far and in which direction did factory i's local training 
 pull the weights away from the global model?"
```

Factories with similar data distributions pull in similar directions. Factories with different distributions pull in different directions. K-means groups factories by their pull direction → natural data-similarity clusters.

---

## `__init__()`

```python
class AdaptiveClustering:
    def __init__(self, k_values=[2, 3], default_k=2):
        self.k_values        = k_values        # candidate k values to try
        self.default_k       = default_k       # fallback if silhouette fails
        self.current_clusters = {}             # {factory_id: cluster_id}
        self.has_fired        = False          # True after first clustering run
```

`has_fired` is checked by `server.py` every round to decide whether to call `_update_cluster_models()`.

---

## `compute_gradients()` — Step 1: Flatten & Subtract

```python
def compute_gradients(self, global_weights, client_weights_dict):
    """
    gradient_i = global_weights_flat - factory_weights_flat
    
    Args:
        global_weights:      list[np.ndarray]  — post-FedAvg model
        client_weights_dict: dict{int: list[np.ndarray]}  — per-factory weights
    
    Returns:
        dict{factory_id: np.ndarray}  — one 1D gradient vector per factory
    """
    # Flatten global weights into a single 1D vector
    global_flat = np.concatenate([w.flatten() for w in global_weights])
    # For CNN1D with 7,714 params: global_flat.shape = (7714,)

    gradients = {}
    for factory_id, client_weights in client_weights_dict.items():
        client_flat = np.concatenate([w.flatten() for w in client_weights])
        gradient    = global_flat - client_flat
        # Positive value: factory pulled this parameter DOWN from global
        # Negative value: factory pulled this parameter UP from global
        gradients[factory_id] = gradient

    return gradients
    # Returns: {1: array(7714,), 2: array(7714,), 3: array(7714,), 4: array(7714,)}
```

---

## `run_clustering()` — Step 2: Normalize → K-Means → Silhouette

```python
def run_clustering(self, gradients, round_num):
    factory_ids = list(gradients.keys())   # [1, 2, 3, 4]

    # Stack into matrix: (n_factories, n_parameters)
    gradient_matrix = np.stack([gradients[fid] for fid in factory_ids])
    # Shape: (4, 7714)

    # L2-normalize each row (factory) to unit length
    gradient_matrix = normalize(gradient_matrix, norm='l2')
    # After: every row has ||row|| = 1.0
    # This makes K-means cluster by DIRECTION, not magnitude
    # (factory with more data → larger gradient magnitude → but same direction)
```

### Why L2-normalize?

```
Without normalization:
  Factory 2 (100 engines) gradient magnitude ≈ 0.05
  Factory 3 (100 engines) gradient magnitude ≈ 0.05
  Factory 4 (100 engines) gradient magnitude ≈ 0.06
  → K-means treats magnitudes as distance → groups by amount of change
  
With L2-normalization:
  All factories → unit length vectors on 7714-dimensional unit sphere
  → K-means groups by ANGLE between vectors
  → Angle captures "direction of optimization" = data distribution similarity
```

### K-means Loop with Silhouette Selection

```python
    best_k      = self.default_k   # 2
    best_score  = -1.0
    best_labels = None

    for k in self.k_values:        # try k=2, then k=3
        if k >= len(factory_ids):  # skip if not enough factories
            continue

        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(gradient_matrix)
        # labels: array of cluster IDs, e.g. [0, 1, 0, 1] for k=2

        if len(set(labels)) > 1:   # at least 2 clusters actually formed
            score = silhouette_score(gradient_matrix, labels)
            # Silhouette score: how well each point fits its cluster vs others
            # Formula for point i:
            #   s(i) = (b(i) - a(i)) / max(a(i), b(i))
            #   a(i) = mean distance to own cluster members
            #   b(i) = mean distance to nearest other cluster's members
            #   s(i) ∈ [-1, 1]:  1=perfect, 0=boundary, -1=wrong cluster
            # silhouette_score = mean s(i) across all points
        else:
            score = -1.0  # only 1 cluster formed (degenerate)

        if score > best_score:
            best_score  = score
            best_k      = k
            best_labels = labels
```

**Example for 4 factories:**
```
k=2 trial:
  labels = [0, 1, 0, 1]   (FD001+FD003 in cluster 0, FD002+FD004 in cluster 1)
  silhouette_score ≈ 0.41  ← chosen as best

k=3 trial:
  labels = [0, 1, 0, 2]   (FD001+FD003 together, FD002 alone, FD004 alone)
  silhouette_score ≈ 0.28  ← worse
  
Winner: k=2, silhouette=0.41
```

### Fallback

```python
    if best_labels is None:
        # Nothing worked (e.g. all silhouettes negative)
        kmeans      = KMeans(n_clusters=self.default_k, random_state=42, n_init=10)
        best_labels = kmeans.fit_predict(gradient_matrix)
        best_k      = self.default_k
        best_score  = 0.0
```

---

## Step 3: Build Assignments → Log → Return

```python
    # Map factory_ids back to cluster labels
    assignments = {
        factory_ids[i]: int(best_labels[i])
        for i in range(len(factory_ids))
    }
    # Example: {1: 0, 2: 1, 3: 0, 4: 1}

    # Write to PostgreSQL — one row per factory
    for factory_id, cluster_id in assignments.items():
        log_cluster_assignment(
            round_num        = round_num,
            factory_id       = factory_id,
            cluster_id       = cluster_id,
            silhouette_score = float(best_score),
            k_value          = int(best_k),
            reason           = "plateau_detected"
        )
    # Also updates factories.cluster_id column

    self.current_clusters = assignments   # stored for subsequent rounds
    self.has_fired = True                 # prevents re-triggering

    return assignments, best_score, best_k
```

---

## Full Algorithm Pseudocode

```
INPUT:
  global_weights  = FedAvg result from this round (7714 params)
  client_weights  = {1: w1, 2: w2, 3: w3, 4: w4}  (per-factory, 7714 params each)

STEP 1 — Compute gradients:
  FOR each factory i:
    gradient_i = global_weights_flat - factory_i_weights_flat
  → gradient matrix G of shape (4, 7714)

STEP 2 — Normalize:
  FOR each row in G:
    row = row / ||row||₂
  → unit-length gradient matrix G_norm of shape (4, 7714)

STEP 3 — Try k=2:
  KMeans(k=2).fit(G_norm) → labels_2
  s_2 = silhouette_score(G_norm, labels_2)

STEP 4 — Try k=3:
  KMeans(k=3).fit(G_norm) → labels_3
  s_3 = silhouette_score(G_norm, labels_3)

STEP 5 — Select best k:
  IF s_2 > s_3: use labels_2 (k=2)
  ELSE:         use labels_3 (k=3)

STEP 6 — Log and return:
  assignments = {1→cluster, 2→cluster, 3→cluster, 4→cluster}
  WRITE to cluster_assignments table
  SET has_fired = True

OUTPUT:
  assignments (dict), silhouette_score (float), k (int)
```

---

## Why This Consistently Produces {FD001,FD003} and {FD002,FD004}

The gradient direction for each factory encodes its data distribution's influence on the global model:

```
FD001 gradient direction: pulls toward "reduce HPC temperature sensitivity"
                           "increase specificity for 1 operating condition"
FD003 gradient direction: pulls toward "reduce HPC+Fan temperature sensitivity"
                           "increase specificity for 1 operating condition"
→ FD001 and FD003 point in similar directions (same operating condition count)

FD002 gradient direction: pulls toward "generalize across 6 altitude levels"
                           "normalize for multi-condition sensor variation"
FD004 gradient direction: pulls toward same multi-condition normalization
→ FD002 and FD004 point in similar directions

Cosine similarity FD001↔FD003 >> cosine similarity FD001↔FD002
→ K-means reliably separates them into 2 clusters
```
