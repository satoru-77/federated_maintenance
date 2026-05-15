# server.py
import argparse
import yaml
import numpy as np
import flwr as fl
from typing import List, Tuple, Optional, Dict
from flwr.server.client_proxy import ClientProxy
from flwr.common import FitRes
from flwr.common import parameters_to_ndarrays, ndarrays_to_parameters


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db_logger import log_round, log_round_summary
from server.clustering import AdaptiveClustering
from server.cluster_models import ClusterModelManager
from server.personalization import PersonalizationManager
from server.security import ByzantineDetector


def load_config():
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config.yaml'
    )
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


class FLServer(fl.server.strategy.FedAvg):

    def __init__(self, algorithm="FedAvg", **kwargs):
        super().__init__(**kwargs)
        self.algorithm        = algorithm
        self.round_accuracies = []
        self.current_round    = 0

        self.latest_client_weights: Dict[int, List[np.ndarray]] = {}
        self.latest_client_samples: Dict[int, int] = {}

        config = load_config()
        self.plateau_patience = config['fl']['plateau_patience']
        self.plateau_delta    = config['fl']['plateau_delta']

        self.clustering      = AdaptiveClustering(
            k_values  = config['clustering']['k_values'],
            default_k = config['clustering']['default_k']
        )
        self.cluster_manager  = ClusterModelManager()
        self.global_weights: Optional[List[np.ndarray]] = None

        self.personalization       = PersonalizationManager()
        self.personalization_round = None
        self.byzantine_detector    = ByzantineDetector(threshold=0.5)
        self.current_true_acc      = None  # set in aggregate_fit each round

        print(f"\n[Server] Strategy: {algorithm}")
        print(f"[Server] Plateau patience: {self.plateau_patience} rounds")

    def aggregate_fit(
        self,
        server_round: int,
        results: List[Tuple[ClientProxy, FitRes]],
        failures,
    ):
        self.current_round = server_round
        print(f"")
        print(f"  ---- Round {server_round} -----------------------------------------------")
        print(f"  [Aggregation] Collecting results from {len(results)} clients...")

        if not results:
            return None, {}

        for client_proxy, fit_res in results:
            factory_id = int(fit_res.metrics.get("factory_id", 0))
            accuracy   = float(fit_res.metrics.get("accuracy", 0.0))
            loss       = float(fit_res.metrics.get("loss", 0.0))
            n_samples  = fit_res.num_examples

            weights = parameters_to_ndarrays(fit_res.parameters)
            if factory_id > 0:
                self.latest_client_weights[factory_id] = weights
                self.latest_client_samples[factory_id] = n_samples

                cluster_id = self.clustering.current_clusters.get(
                    factory_id, None
                )
                log_round(
                    round_num  = server_round,
                    factory_id = factory_id,
                    algorithm  = self.algorithm,
                    accuracy   = accuracy,
                    loss       = loss,
                    n_samples  = n_samples,
                    cluster_id = cluster_id
                )

        # Byzantine detection
        if len(self.latest_client_weights) >= 2:
            print(f"")
            print(f"  [Byzantine] Running cosine similarity check on {len(self.latest_client_weights)} clients...")
            clean_ids, flagged_ids, scores = self.byzantine_detector.detect(
                self.latest_client_weights, server_round
            )
            if flagged_ids:
                print(f"  [Byzantine] FLAGGED factories excluded from aggregation: {flagged_ids}")
                
                # Broadast to dashboard so the bubble turns red!
                try:
                    import requests
                    requests.post("http://localhost:8000/ws/broadcast", json={
                        "type": "byzantine_alert",
                        "factory_id": int(flagged_ids[0])
                    }, timeout=2)
                except Exception:
                    pass

                # Exclude from global aggregation
                results = [
                    (cp, fr) for cp, fr in results
                    if int(fr.metrics.get("factory_id", 0)) not in flagged_ids
                ]
                # Also completely delete their bad weights so they don't ruin clustering!
                for fid in flagged_ids:
                    if fid in self.latest_client_weights:
                        del self.latest_client_weights[fid]
                    if fid in self.latest_client_samples:
                        del self.latest_client_samples[fid]

        # Standard FedAvg aggregation for global model
        aggregated = super().aggregate_fit(server_round, results, failures)

        if aggregated[0] is not None:
            self.global_weights = parameters_to_ndarrays(aggregated[0])

        if self.clustering.has_fired:
            self._update_cluster_models()

        # Calculate sample-weighted accuracy — matches the dashboard calculation exactly
        total_samples = sum(fr.num_examples for _, fr in results)
        if total_samples > 0:
            self.current_true_acc = sum(
                float(fr.metrics.get("accuracy", 0.0)) * fr.num_examples
                for _, fr in results
            ) / total_samples

        return aggregated

    def _update_cluster_models(self):
        clusters = self.clustering.current_clusters
        cluster_groups: Dict[int, List[int]] = {}
        for factory_id, cluster_id in clusters.items():
            if cluster_id not in cluster_groups:
                cluster_groups[cluster_id] = []
            cluster_groups[cluster_id].append(factory_id)

        print(f"")
        print(f"  [Clustering] Factory assignments (k={len(cluster_groups)}):")
        for cluster_id, factory_ids in cluster_groups.items():
            print(f"    Cluster {cluster_id} : {factory_ids}")
            weights_list   = []
            n_samples_list = []
            for fid in factory_ids:
                if fid in self.latest_client_weights:
                    weights_list.append(self.latest_client_weights[fid])
                    n_samples_list.append(self.latest_client_samples[fid])
            if weights_list:
                self.cluster_manager.update_cluster_model(
                    cluster_id, weights_list, n_samples_list
                )
                total_s = sum(n_samples_list)
                print(f"    Cluster {cluster_id} model updated  | {len(weights_list)} factories | {total_s:,} samples")

    def aggregate_evaluate(
        self,
        server_round: int,
        results,
        failures,
    ):
        if not results:
            return None, {}

        accs = []
        for item1, item2 in results:
            if hasattr(item2, 'num_examples'):
                res = item2
                num = item2.num_examples
            else:
                res = item1
                num = item1.num_examples
            acc = res.metrics.get("accuracy", 0.0)
            accs.append((num, acc))

        total = sum(n for n, _ in accs)
        w_acc = sum(n * a for n, a in accs) / total if total > 0 else 0.0

        self.round_accuracies.append(w_acc)

        # Persist both metrics to DB so the dashboard can show them live
        clustered = self.current_true_acc if self.current_true_acc is not None else w_acc
        log_round_summary(
            round_num          = server_round,
            clustered_accuracy = clustered,
            naive_global       = w_acc,
            n_clients          = len(results),
            clustering_fired   = self.clustering.has_fired
        )

        print(f"\n[Server] Round {server_round} Results:")

        if not self.clustering.has_fired:
            print(f"  [Metrics] Global Model Accuracy          : {w_acc:.4f}")
            print(f"  [Metrics] Participating Clients          : {len(results)}")
        else:
            print(f"  [Metrics] Clustered Network Accuracy     : {clustered:.4f}  (personalized, per-cluster models)")
            print(f"  [Metrics] Naive Global Baseline          : {w_acc:.4f}  (what accuracy would be without clustering)")
            print(f"  [Metrics] Participating Clients          : {len(results)}")

        if not self.clustering.has_fired:
            if server_round >= 8 and self._is_plateau():
                print(f"\n[Server] Accuracy plateau detected — triggering adaptive clustering")
                self._trigger_clustering(server_round)
            elif server_round == 10:
                print(f"\n[Server] Round 10 hard trigger — running adaptive clustering")
                self._trigger_clustering(server_round)

        pass

        return None, {"accuracy": w_acc}

    def _run_personalization(self, server_round):
        if self.personalization.has_run:
            return
        if not self.clustering.has_fired:
            return
        if not self.latest_client_weights:
            return

        print(f"\n[Server] === Running personalization at round {server_round} ===")

        from client.model import FailureCNN
        from client.data_loader import load_factory_data

        for factory_id, local_weights in self.latest_client_weights.items():
            cluster_id = self.clustering.current_clusters.get(factory_id)
            if cluster_id is None:
                continue

            cluster_weights = self.cluster_manager.get_cluster_weights(cluster_id)
            if cluster_weights is None:
                continue

            try:
                _, X_val, _, y_val, _, _ = load_factory_data(
                    factory_id, data_dir='./client'
                )
            except Exception as e:
                print(f"  [Personalization] Factory {factory_id} data error: {e}")
                continue

            model = FailureCNN(n_sensors=14, seq_length=30)

            self.personalization.run_personalization(
                factory_id      = factory_id,
                cluster_weights = cluster_weights,
                local_weights   = local_weights,
                model           = model,
                X_val           = X_val,
                y_val           = y_val
            )

            # Clear memory after EACH factory — inside the loop
            del model, X_val, y_val
            import gc
            gc.collect()


        self.personalization.has_run   = True
        self.personalization_round     = server_round
        self.personalization.get_summary()
        print(f"[Server] Personalization complete!")

    def _trigger_clustering(self, round_num):
        if self.global_weights is None:
            print("[Server] No global weights — skipping")
            return
        if len(self.latest_client_weights) < 2:
            print("[Server] Not enough weights — skipping")
            return

        gradients = self.clustering.compute_gradients(
            self.global_weights,
            self.latest_client_weights
        )
        assignments, score, k = self.clustering.run_clustering(
            gradients, round_num
        )
        print(f"\n[Server] Clustering complete!")

    def _is_plateau(self):
        if len(self.round_accuracies) < self.plateau_patience:
            return False
        recent      = self.round_accuracies[-self.plateau_patience:]
        improvement = max(recent) - min(recent)
        return improvement < self.plateau_delta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds",         type=int, default=20)
    parser.add_argument("--algorithm",      type=str, default="FedAvg",
                        choices=["FedAvg", "FedProx"])
    parser.add_argument("--server-address", type=str, default="0.0.0.0:8080")
    args = parser.parse_args()

    config = load_config()

    print(f"\n{'='*50}")
    print(f"FL Server starting")
    print(f"Algorithm:  {args.algorithm}")
    print(f"Rounds:     {args.rounds}")
    print(f"Min clients:{config['fl']['min_clients']}")
    print(f"{'='*50}\n")

    strategy = FLServer(
        algorithm             = args.algorithm,
        min_fit_clients       = config['fl']['min_clients'],
        min_evaluate_clients  = config['fl']['min_clients'],
        min_available_clients = config['fl']['min_clients'],
        on_fit_config_fn      = lambda r: {
            "local_epochs": config['fl']['local_epochs'],
            "round":        r
        },
    )

    fl.server.start_server(
        server_address = args.server_address,
        config         = fl.server.ServerConfig(num_rounds=args.rounds),
        strategy       = strategy,
    )


if __name__ == "__main__":
    main()