# security.py
# Security components for the FL system
# 1. Differential Privacy — noise injection on client side
# 2. Byzantine Fault Detection — bad client detection on server side

import numpy as np
from typing import List, Dict, Tuple


# ─────────────────────────────────────────────────────────────
# DIFFERENTIAL PRIVACY
# ─────────────────────────────────────────────────────────────

class DifferentialPrivacy:
    """
    Adds Gaussian noise to model weights before sharing.
    
    Why this works:
    Even if an attacker intercepts the weights, they cannot
    reconstruct the original sensor data because the noise
    makes the weights statistically indistinguishable from
    weights trained on slightly different data.
    
    The privacy guarantee is parameterized by epsilon (ε):
    - Small ε (e.g. 0.1) = strong privacy, more noise, lower accuracy
    - Large ε (e.g. 10.0) = weak privacy, less noise, higher accuracy
    - Our default ε = 1.0 = reasonable balance
    """

    def __init__(self, epsilon=1.0, delta=1e-5, sensitivity=1.0):
        self.epsilon     = epsilon      # privacy budget
        self.delta       = delta        # failure probability
        self.sensitivity = sensitivity  # L2 sensitivity of the weights

        # Compute noise scale using Gaussian mechanism
        # sigma = sensitivity * sqrt(2 * ln(1.25/delta)) / epsilon
        import math
        self.sigma = (sensitivity *
                      np.sqrt(2 * math.log(1.25 / delta)) /
                      epsilon)

        self.total_epsilon_spent = 0.0  # track cumulative privacy budget

        print(f"[DP] Initialized: epsilon={epsilon}, sigma={self.sigma:.4f}")

    def add_noise(self, weights: List[np.ndarray]) -> List[np.ndarray]:
        """
        Add Gaussian noise to each weight array.
        Called by factory clients before sending weights to server.
        
        Args:
            weights: list of numpy arrays (model weights)
        
        Returns:
            noisy_weights: same structure but with noise added
        """
        noisy_weights = []
        for w in weights:
            noise = np.random.normal(0, self.sigma, w.shape).astype(w.dtype)
            noisy_weights.append(w + noise)

        # Track privacy budget consumption
        self.total_epsilon_spent += self.epsilon
        return noisy_weights

    def get_privacy_report(self, factory_id):
        """Return privacy budget status for a factory."""
        return {
            "factory_id":            factory_id,
            "epsilon_per_round":     self.epsilon,
            "total_epsilon_spent":   self.total_epsilon_spent,
            "sigma":                 self.sigma,
            "privacy_level":         self._privacy_level()
        }

    def _privacy_level(self):
        """Human-readable privacy level."""
        if self.epsilon <= 0.5:
            return "Very Strong"
        elif self.epsilon <= 1.0:
            return "Strong"
        elif self.epsilon <= 5.0:
            return "Moderate"
        else:
            return "Weak"


# ─────────────────────────────────────────────────────────────
# BYZANTINE FAULT DETECTION
# ─────────────────────────────────────────────────────────────

class ByzantineDetector:
    """
    Detects factory clients sending anomalous weights.
    
    What is a Byzantine client?
    A factory that sends weights that are very different from
    all other factories — either due to:
    - Data corruption
    - A bug in the local training
    - A malicious actor trying to poison the global model
    
    Detection method: cosine similarity to median
    1. Compute the median weight vector across all factories
    2. Compute cosine similarity of each factory to the median
    3. Factories below the threshold are flagged as suspicious
    
    Flagged factories are excluded from that round's aggregation.
    """

    def __init__(self, threshold=0.5):
        self.threshold       = threshold  # minimum similarity score
        self.flagged_history = []         # list of (round, factory_id) tuples

    def detect(self,
               client_weights: Dict[int, List[np.ndarray]],
               round_num: int
               ) -> Tuple[List[int], List[int], Dict[int, float]]:
        """
        Check all clients for Byzantine behaviour.
        
        Args:
            client_weights: dict {factory_id: list of numpy arrays}
            round_num:      current round number
        
        Returns:
            clean_ids:    list of factory IDs that passed
            flagged_ids:  list of factory IDs that failed
            scores:       dict {factory_id: similarity_score}
        """
        if len(client_weights) < 2:
            # Need at least 2 clients to detect anomalies
            return list(client_weights.keys()), [], {}

        # Flatten all weights into vectors
        factory_ids = list(client_weights.keys())
        flat_weights = {
            fid: np.concatenate([w.flatten() for w in weights])
            for fid, weights in client_weights.items()
        }

        # Compute median weight vector
        weight_matrix = np.stack(list(flat_weights.values()))
        median_vector = np.median(weight_matrix, axis=0)

        # Compute cosine similarity of each factory to median
        scores = {}
        for fid, flat_w in flat_weights.items():
            similarity = self._cosine_similarity(flat_w, median_vector)
            scores[fid] = float(similarity)

        # Flag factories below threshold
        clean_ids   = []
        flagged_ids = []

        for fid, score in scores.items():
            if score < self.threshold:
                flagged_ids.append(fid)
                self.flagged_history.append((round_num, fid, score))
                print(f"  [Byzantine] Factory {fid} FLAGGED - Suspicious weights "
                      f"(similarity={score:.4f} < {self.threshold})")
            else:
                clean_ids.append(fid)
                print(f"  [Byzantine] Factory {fid} OK "
                      f"(similarity={score:.4f})")

        return clean_ids, flagged_ids, scores

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def get_flagged_history(self):
        """Return all flagging events."""
        return [
            {"round": r, "factory_id": f, "score": s}
            for r, f, s in self.flagged_history
        ]