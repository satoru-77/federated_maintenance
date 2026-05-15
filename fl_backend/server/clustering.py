# clustering.py
# Collects gradients from factory clients and runs K-means
# Called by the Flower server after plateau detection

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db_logger import log_cluster_assignment


class AdaptiveClustering:
    """
    Runs K-means clustering on factory gradients.
    
    What is a gradient here?
    After local training, each factory's weights have shifted 
    from the global model. The gradient = that shift direction.
    Factories with similar data shift in similar directions.
    K-means groups factories by how similarly they shift.
    """

    def __init__(self, k_values=[2, 3], default_k=2):
        self.k_values  = k_values   # which k values to try
        self.default_k = default_k  # k to use if silhouette fails
        self.current_clusters = {}  # factory_id → cluster_id
        self.has_fired = False       # has clustering run yet?

    def compute_gradients(self, global_weights, client_weights_dict):
        """
        Compute gradient vector for each factory.
        
        gradient_i = global_weights_flat - factory_weights_flat
        
        This tells us: in which direction did each factory
        try to pull the global model?

        Args:
            global_weights:      list of numpy arrays (global model)
            client_weights_dict: dict {factory_id: list of numpy arrays}
        
        Returns:
            dict {factory_id: gradient_vector (1D numpy array)}
        """
        # Flatten global weights into one long vector
        global_flat = np.concatenate([w.flatten() for w in global_weights])

        gradients = {}
        for factory_id, client_weights in client_weights_dict.items():
            # Flatten this factory's weights
            client_flat = np.concatenate([w.flatten() for w in client_weights])
            
            # Gradient = difference between global and local
            gradient = global_flat - client_flat
            gradients[factory_id] = gradient

        return gradients

    def run_clustering(self, gradients, round_num):
        """
        Run K-means on gradient vectors, pick best k.
        
        Args:
            gradients: dict {factory_id: gradient_vector}
            round_num: int, current FL round number
        
        Returns:
            dict {factory_id: cluster_id}
            float: silhouette score of chosen clustering
            int: chosen k
        """
        factory_ids = list(gradients.keys())
        
        # Stack gradients into a matrix: (n_factories, n_parameters)
        gradient_matrix = np.stack([gradients[fid] for fid in factory_ids])
        
        # Normalize each gradient vector (unit length)
        # This makes clustering focus on DIRECTION not magnitude
        gradient_matrix = normalize(gradient_matrix, norm='l2')
        
        print(f"\n[Clustering] Running K-means on gradients...")
        print(f"[Clustering] Gradient matrix shape: {gradient_matrix.shape}")
        print(f"[Clustering] Factories: {factory_ids}")

        # Try each k value, pick the one with best silhouette score
        best_k          = self.default_k
        best_score      = -1.0
        best_labels     = None

        # Need at least 2 samples per cluster for silhouette
        max_k = min(max(self.k_values), len(factory_ids) - 1)

        for k in self.k_values:
            if k >= len(factory_ids):
                print(f"[Clustering] Skipping k={k} (not enough factories)")
                continue
            if k < 2:
                continue

            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(gradient_matrix)

            # Silhouette score: how well-separated are the clusters?
            # -1 = terrible, 0 = overlapping, 1 = perfect separation
            if len(set(labels)) > 1:
                score = silhouette_score(gradient_matrix, labels)
                print(f"[Clustering] k={k}: silhouette={score:.4f}")
            else:
                score = -1.0
                print(f"[Clustering] k={k}: only 1 cluster formed")

            if score > best_score:
                best_score  = score
                best_k      = k
                best_labels = labels

        # Fall back to k=2 if nothing worked
        if best_labels is None:
            print(f"[Clustering] Falling back to k={self.default_k}")
            kmeans      = KMeans(n_clusters=self.default_k,
                                 random_state=42, n_init=10)
            best_labels = kmeans.fit_predict(gradient_matrix)
            best_k      = self.default_k
            best_score  = 0.0

        # Build factory_id → cluster_id mapping
        assignments = {
            factory_ids[i]: int(best_labels[i])
            for i in range(len(factory_ids))
        }

        print(f"\n[Clustering] *** CLUSTERING RESULT (k={best_k}) ***")
        for fid, cid in assignments.items():
            print(f"[Clustering]   Factory {fid} → Cluster {cid}")
        print(f"[Clustering] Silhouette score: {best_score:.4f}")

        # Log to PostgreSQL
        for factory_id, cluster_id in assignments.items():
            log_cluster_assignment(
                round_num        = round_num,
                factory_id       = factory_id,
                cluster_id       = cluster_id,
                silhouette_score = float(best_score),
                k_value          = int(best_k),
                reason           = "plateau_detected"
            )

        self.current_clusters = assignments
        self.has_fired = True

        return assignments, best_score, best_k