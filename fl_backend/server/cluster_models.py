# cluster_models.py
# Manages separate models for each cluster after clustering fires
# Each cluster gets its own FedAvg aggregation

import numpy as np
from typing import Dict, List


class ClusterModelManager:
    """
    After clustering fires, each cluster maintains its own model.
    
    Instead of one global model for all 4 factories:
    - Cluster 0 model: aggregated from Cluster 0 factories only
    - Cluster 1 model: aggregated from Cluster 1 factories only
    
    This is what makes accuracy improve after clustering.
    """

    def __init__(self):
        self.cluster_weights: Dict[int, List[np.ndarray]] = {}
        # cluster_id → list of numpy arrays (model weights)

    def update_cluster_model(self, cluster_id, factory_weights_list,
                              n_samples_list):
        """
        Aggregate weights for one cluster using weighted FedAvg.
        
        Only called with weights from factories IN this cluster.
        
        Args:
            cluster_id:          int
            factory_weights_list: list of weight lists (one per factory)
            n_samples_list:      list of ints (samples per factory)
        """
        if not factory_weights_list:
            return

        total_samples = sum(n_samples_list)
        if total_samples == 0:
            return

        # Weighted average of weights
        # Factories with more data have more influence
        aggregated = []
        for layer_idx in range(len(factory_weights_list[0])):
            layer_avg = sum(
                (n / total_samples) * factory_weights_list[i][layer_idx]
                for i, n in enumerate(n_samples_list)
            )
            aggregated.append(layer_avg)

        self.cluster_weights[cluster_id] = aggregated
        print(f"  [ClusterModels] Cluster {cluster_id} model updated "
              f"({len(factory_weights_list)} factories, "
              f"{total_samples} samples)")

    def get_cluster_weights(self, cluster_id):
        """
        Return the current model weights for a cluster.
        Returns None if cluster has no model yet.
        """
        return self.cluster_weights.get(cluster_id, None)

    def has_model(self, cluster_id):
        """Check if a cluster has a model yet."""
        return cluster_id in self.cluster_weights

    def get_all_clusters(self):
        """Return list of cluster IDs that have models."""
        return list(self.cluster_weights.keys())