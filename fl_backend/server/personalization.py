# personalization.py
# Finds the best alpha value for each factory via grid search
# Called after clustering stabilises (around round 15+)

import numpy as np
import torch
import torch.nn as nn
from collections import OrderedDict

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db_logger import update_factory_alpha


def blend_weights(cluster_weights, local_weights, alpha):
    """
    Blend cluster model and local model weights.
    
    formula: blended = α * cluster + (1-α) * local
    
    Args:
        cluster_weights: list of numpy arrays (cluster model)
        local_weights:   list of numpy arrays (local model)
        alpha:           float between 0 and 1
    
    Returns:
        list of numpy arrays (blended weights)
    """
    blended = []
    for cw, lw in zip(cluster_weights, local_weights):
        blended.append(alpha * cw + (1 - alpha) * lw)
    return blended


def evaluate_weights(model, weights, X_val, y_val):
    """
    Load weights into model and evaluate on validation data.
    Returns accuracy.
    
    Args:
        model:   FailureCNN instance
        weights: list of numpy arrays
        X_val:   numpy array shape (n, 30, 14)
        y_val:   numpy array shape (n,)
    
    Returns:
        float: accuracy on validation set
    """
    # Load weights into model
    params_dict = zip(model.state_dict().keys(), weights)
    state_dict  = OrderedDict(
        {k: torch.tensor(v) for k, v in params_dict}
    )
    model.load_state_dict(state_dict, strict=True)
    model.eval()

    X_tensor = torch.FloatTensor(X_val)
    
    with torch.no_grad():
        outputs = model(X_tensor)
        probs   = torch.softmax(outputs, dim=1)[:, 1].numpy()
        preds   = (probs > 0.4).astype(int)
    
    accuracy = float((preds == y_val).mean())
    return accuracy


def grid_search_alpha(factory_id, cluster_weights, local_weights,
                      model, X_val, y_val,
                      alpha_values=None):
    """
    Try different alpha values and find the best one.
    
    Args:
        factory_id:      int
        cluster_weights: list of numpy arrays
        local_weights:   list of numpy arrays
        model:           FailureCNN instance
        X_val:           validation features
        y_val:           validation labels
        alpha_values:    list of floats to try (default 0.1 to 0.9)
    
    Returns:
        best_alpha: float
        best_accuracy: float
        all_results: dict {alpha: accuracy}
    """
    if alpha_values is None:
        alpha_values = [round(a * 0.1, 1) for a in range(1, 10)]
        # [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    print(f"\n[Personalization] Factory {factory_id} — grid search alpha")
    
    all_results   = {}
    best_alpha    = 0.5
    best_accuracy = 0.0

    # Use only 20% of validation data for speed and memory
    max_samples = min(len(X_val), 2000)
    X_val = X_val[:max_samples]
    y_val = y_val[:max_samples]

    for alpha in alpha_values:
        # Blend the two models
        blended = blend_weights(cluster_weights, local_weights, alpha)
        
        # Evaluate blended model
        accuracy = evaluate_weights(model, blended, X_val, y_val)
        all_results[alpha] = accuracy

        print(f"  α={alpha:.1f} → accuracy={accuracy:.4f}")

        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_alpha    = alpha

    print(f"  Best: α={best_alpha:.1f} → accuracy={best_accuracy:.4f}")

    # Save best alpha to database
    update_factory_alpha(factory_id, best_alpha)

    return best_alpha, best_accuracy, all_results


class PersonalizationManager:
    """
    Manages personalization for all factories.
    Called by the server after clustering stabilises.
    """

    def __init__(self):
        self.best_alphas    = {}   # factory_id → best alpha
        self.best_accuracies = {}  # factory_id → best accuracy
        self.has_run        = False

    def run_personalization(self, factory_id, cluster_weights,
                            local_weights, model, X_val, y_val):
        """
        Run grid search for one factory.
        Store best alpha and accuracy.
        """
        best_alpha, best_acc, results = grid_search_alpha(
            factory_id     = factory_id,
            cluster_weights= cluster_weights,
            local_weights  = local_weights,
            model          = model,
            X_val          = X_val,
            y_val          = y_val
        )
        self.best_alphas[factory_id]     = best_alpha
        self.best_accuracies[factory_id] = best_acc
        return best_alpha, best_acc

    def get_summary(self):
        """Print summary of personalization results."""
        print("\n[Personalization] === SUMMARY ===")
        for fid in sorted(self.best_alphas.keys()):
            print(f"  Factory {fid}: "
                  f"best α={self.best_alphas[fid]:.1f}, "
                  f"accuracy={self.best_accuracies[fid]:.4f}")