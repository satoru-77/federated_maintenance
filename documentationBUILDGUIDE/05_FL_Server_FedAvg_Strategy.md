# 05 — FL Server: FedAvg Strategy & Round Orchestration (`server.py`)

**File:** `fl_backend/server/server.py`  
**Entry point:** `python -m server.server --rounds 20 --algorithm FedAvg`  
**Class:** `FLServer(fl.server.strategy.FedAvg)` — extends Flower's built-in FedAvg  
**Port:** `8080` (gRPC — factory clients connect here)

---

## Architecture: What FLServer Extends

```
flwr.server.strategy.FedAvg  (Flower built-in)
    └── FLServer              (our custom strategy)
          ├── aggregate_fit()     ← called after every training round
          ├── aggregate_evaluate() ← called after every eval round
          ├── _trigger_clustering() ← fires at round 10 or plateau
          ├── _update_cluster_models() ← re-computes cluster-specific weights
          ├── _run_personalization() ← alpha grid search per factory
          └── _is_plateau()       ← detects accuracy stagnation
```

---

## Initialization

```python
class FLServer(fl.server.strategy.FedAvg):
    def __init__(self, algorithm="FedAvg", **kwargs):
        super().__init__(**kwargs)      # passes min_fit_clients etc to FedAvg
        self.algorithm        = algorithm
        self.round_accuracies = []      # running list of weighted accs per round
        self.current_round    = 0

        # Per-round weight snapshots (cleared each round)
        self.latest_client_weights: Dict[int, List[np.ndarray]] = {}
        self.latest_client_samples: Dict[int, int] = {}

        # Load all tunable params from config.yaml
        config = load_config()
        self.plateau_patience = config['fl']['plateau_patience']  # 4
        self.plateau_delta    = config['fl']['plateau_delta']     # 0.02

        # Sub-systems
        self.clustering        = AdaptiveClustering(k_values=[2,3], default_k=2)
        self.cluster_manager   = ClusterModelManager()
        self.global_weights    = None    # latest aggregated global weights
        self.personalization   = PersonalizationManager()
        self.byzantine_detector = ByzantineDetector(threshold=0.5)
        self.current_true_acc  = None   # set in aggregate_fit each round
```

---

## `aggregate_fit()` — Per-Round Training Aggregation

Called by Flower after all factory clients complete their local training.

```python
def aggregate_fit(self, server_round, results, failures):
    self.current_round = server_round
```

### Step 1: Unpack client results

```python
for client_proxy, fit_res in results:
    factory_id = int(fit_res.metrics.get("factory_id", 0))
    accuracy   = float(fit_res.metrics.get("accuracy", 0.0))
    loss       = float(fit_res.metrics.get("loss", 0.0))
    n_samples  = fit_res.num_examples

    weights = parameters_to_ndarrays(fit_res.parameters)
    # parameters_to_ndarrays: converts Flower's binary Parameters → list of np.ndarray

    self.latest_client_weights[factory_id] = weights   # save for clustering/personalization
    self.latest_client_samples[factory_id] = n_samples

    cluster_id = self.clustering.current_clusters.get(factory_id, None)
    log_round(round_num, factory_id, algorithm, accuracy, loss, n_samples, cluster_id)
    # → writes 1 row to PostgreSQL training_rounds table
    # → broadcasts WebSocket "round_complete" event to all connected browsers
```

### Step 2: Byzantine detection

```python
if len(self.latest_client_weights) >= 2:
    clean_ids, flagged_ids, scores = self.byzantine_detector.detect(
        self.latest_client_weights, server_round
    )

    if flagged_ids:
        # Broadcast alert to dashboard (bubble turns red)
        requests.post("http://localhost:8000/ws/broadcast", json={
            "type": "byzantine_alert",
            "factory_id": int(flagged_ids[0])
        }, timeout=2)

        # Exclude flagged factories from this round's FedAvg
        results = [(cp, fr) for cp, fr in results
                   if int(fr.metrics.get("factory_id", 0)) not in flagged_ids]

        # Delete their weights (don't let bad weights pollute clustering)
        for fid in flagged_ids:
            del self.latest_client_weights[fid]
            del self.latest_client_samples[fid]
```

### Step 3: FedAvg aggregation (parent class)

```python
aggregated = super().aggregate_fit(server_round, results, failures)
# Flower's built-in: weighted average of weights by n_samples
# For each layer parameter:
#   aggregated[l] = Σ(n_i × w_i[l]) / Σ(n_i)

if aggregated[0] is not None:
    self.global_weights = parameters_to_ndarrays(aggregated[0])
```

### Step 4: Cluster model update (if clustering has fired)

```python
if self.clustering.has_fired:
    self._update_cluster_models()
    # re-runs FedAvg within each cluster group
```

### Step 5: Compute weighted accuracy (for dashboard)

```python
total_samples = sum(fr.num_examples for _, fr in results)
self.current_true_acc = sum(
    float(fr.metrics.get("accuracy", 0.0)) * fr.num_examples
    for _, fr in results
) / total_samples
# Stored in DB as "clustered_accuracy" in round_summaries
```

---

## `aggregate_evaluate()` — Global Model Evaluation

Called by Flower after all factories evaluate the current global model:

```python
def aggregate_evaluate(self, server_round, results, failures):
    # Compute weighted average accuracy of GLOBAL model across all factories
    total = sum(n for n, _ in accs)
    w_acc = sum(n * a for n, a in accs) / total

    self.round_accuracies.append(w_acc)   # used by _is_plateau()

    # Write both metrics to DB
    log_round_summary(
        round_num          = server_round,
        clustered_accuracy = self.current_true_acc,   # local training acc
        naive_global       = w_acc,                   # global model eval acc
        n_clients          = len(results),
        clustering_fired   = self.clustering.has_fired
    )

    # Check if clustering should fire
    if not self.clustering.has_fired:
        if server_round >= 8 and self._is_plateau():
            self._trigger_clustering(server_round)   # early trigger
        elif server_round == 10:
            self._trigger_clustering(server_round)   # hard trigger at round 10
```

**Two accuracy columns explained:**
```
clustered_accuracy = self.current_true_acc
    → weighted avg of each factory's LOCAL training accuracy (from aggregate_fit)
    → "how well are the personalized models fitting local data?"
    → shown as the PRIMARY accuracy on the dashboard

naive_global = w_acc
    → Flower's eval: global averaged weights tested on each factory's val data
    → "how well does the naive global model perform?"
    → shown as the COMPARISON line on the dashboard
```

---

## `_is_plateau()` — Stagnation Detection

```python
def _is_plateau(self):
    if len(self.round_accuracies) < self.plateau_patience:   # need at least 4 rounds
        return False
    recent      = self.round_accuracies[-self.plateau_patience:]  # last 4
    improvement = max(recent) - min(recent)
    return improvement < self.plateau_delta   # < 0.02 = plateau
```

**Example:**
```
Round 8 accuracies: [0.612, 0.621, 0.624, 0.625, 0.625, 0.624, 0.625, 0.626]
Last 4: [0.624, 0.625, 0.624, 0.625, 0.626]
improvement = 0.626 - 0.624 = 0.002 < 0.02 → IS PLATEAU → cluster fires
```

---

## `_trigger_clustering()` — Clustering Entry Point

```python
def _trigger_clustering(self, round_num):
    if self.global_weights is None or len(self.latest_client_weights) < 2:
        return

    # Step 1: Compute gradient = client_weights - global_weights (per layer)
    gradients = self.clustering.compute_gradients(
        self.global_weights,
        self.latest_client_weights
    )

    # Step 2: K-means on gradient vectors
    assignments, score, k = self.clustering.run_clustering(gradients, round_num)
    # assignments = {factory_id: cluster_id}
```

---

## `_update_cluster_models()` — Per-Cluster FedAvg

After clustering fires, each cluster gets its own FedAvg model:

```python
def _update_cluster_models(self):
    clusters = self.clustering.current_clusters
    # e.g. {1: 0, 2: 1, 3: 0, 4: 1}

    cluster_groups = {}
    for factory_id, cluster_id in clusters.items():
        cluster_groups.setdefault(cluster_id, []).append(factory_id)
    # {0: [1, 3], 1: [2, 4]}

    for cluster_id, factory_ids in cluster_groups.items():
        weights_list   = [self.latest_client_weights[fid] for fid in factory_ids
                          if fid in self.latest_client_weights]
        n_samples_list = [self.latest_client_samples[fid] for fid in factory_ids
                          if fid in self.latest_client_samples]

        self.cluster_manager.update_cluster_model(
            cluster_id, weights_list, n_samples_list
        )
        # Runs FedAvg within this cluster:
        # cluster_model[l] = Σ(n_i × w_i[l]) / Σ(n_i)  for i in cluster
```

---

## `main()` — Server Startup

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds",         type=int, default=20)
    parser.add_argument("--algorithm",      type=str, default="FedAvg",
                        choices=["FedAvg", "FedProx"])
    parser.add_argument("--server-address", type=str, default="0.0.0.0:8080")
    args = parser.parse_args()

    strategy = FLServer(
        algorithm             = args.algorithm,
        min_fit_clients       = 4,    # all 4 factories must participate
        min_evaluate_clients  = 4,
        min_available_clients = 4,
        on_fit_config_fn      = lambda r: {
            "local_epochs": 10,
            "round":        r
        },
        # on_fit_config_fn: called before each round, sends config to clients
    )

    fl.server.start_server(
        server_address = "0.0.0.0:8080",
        config         = fl.server.ServerConfig(num_rounds=20),
        strategy       = strategy,
    )
```

---

## Full Round Sequence

```
Round N begins:
    Server → sends global weights to all 4 factories
    Each factory → trains locally for 10 epochs → sends back weights + metrics

aggregate_fit() fires:
    1. Unpacks metrics (factory_id, accuracy, loss, n_samples)
    2. Logs each factory's result to PostgreSQL → broadcasts WS "round_complete"
    3. Byzantine check: cosine similarity to median
    4. FedAvg: weighted average of clean factory weights
    5. Saves new global_weights
    6. If clustering.has_fired: re-runs per-cluster FedAvg
    7. Computes weighted accuracy for this round

aggregate_evaluate() fires:
    1. Receives factories' eval results on GLOBAL model
    2. Computes naive_global accuracy
    3. Logs round_summary to PostgreSQL
    4. Checks plateau: if stagnant for 4 rounds OR round==10 → trigger clustering
    5. Returns {"accuracy": w_acc}

Round N+1 begins → repeat
```
