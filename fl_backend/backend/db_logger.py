# db_logger.py
# Called by the Flower server after each round completes
# Writes round results to PostgreSQL

import requests
from dotenv import load_dotenv
import os
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from .db import SessionLocal
from .models import TrainingRound, Factory, ClusterAssignment, RoundSummary
from datetime import datetime




def log_round(round_num, factory_id, algorithm, accuracy,
              loss, n_samples, cluster_id=None):
    db = SessionLocal()
    try:
        round_entry = TrainingRound(
            round_num  = round_num,
            factory_id = factory_id,
            algorithm  = algorithm,
            accuracy   = accuracy,
            loss       = loss,
            n_samples  = n_samples,
            cluster_id = cluster_id,
            timestamp  = datetime.utcnow()
        )
        db.add(round_entry)
        db.commit()
        print(f"  [DB] Round {round_num} | Factory {factory_id} | "
              f"Acc={accuracy:.4f} | Loss={loss:.4f} | logged")

        # Broadcast to dashboard via WebSocket
        _broadcast_round_event(round_num, factory_id, algorithm,
                               accuracy, loss, cluster_id)

    except Exception as e:
        print(f"  [DB ERROR] Failed to log round: {e}")
        db.rollback()
    finally:
        db.close()


def _broadcast_round_event(round_num, factory_id, algorithm,
                           accuracy, loss, cluster_id):
    """
    Send round event to all connected dashboard browsers.
    Uses a simple HTTP POST to the FastAPI WebSocket broadcaster.
    Non-blocking — if FastAPI is not running, just skip silently.
    """
    try:
        event = {
            "type":       "round_complete",
            "round_num":  round_num,
            "factory_id": factory_id,
            "algorithm":  algorithm,
            "accuracy":   round(accuracy, 4),
            "loss":       round(loss, 4),
            "cluster_id": cluster_id,
            "timestamp":  datetime.utcnow().isoformat()
        }
        requests.post(
            "http://localhost:8000/ws/broadcast",
            json=event,
            timeout=1   # don't block FL training if dashboard is down
        )
    except Exception:
        pass  # silently skip if FastAPI not running


def log_cluster_assignment(round_num, factory_id, cluster_id,
                           silhouette_score, k_value,
                           reason="plateau_detected"):
    db = SessionLocal()
    try:
        factory = db.query(Factory).filter(
            Factory.factory_id == factory_id
        ).first()
        if factory:
            factory.cluster_id = cluster_id

        assignment = ClusterAssignment(
            round_num        = round_num,
            factory_id       = factory_id,
            cluster_id       = cluster_id,
            silhouette_score = silhouette_score,
            k_value          = k_value,
            reason           = reason,
            timestamp        = datetime.utcnow()
        )
        db.add(assignment)
        db.commit()
        print(f"  [DB] Factory {factory_id} assigned to Cluster {cluster_id} "
              f"(silhouette={silhouette_score:.3f}) logged")

        # Broadcast to dashboard
        _broadcast_cluster_event(round_num, factory_id, cluster_id,
                                 silhouette_score, k_value)

    except Exception as e:
        print(f"  [DB ERROR] Failed to log cluster: {e}")
        db.rollback()
    finally:
        db.close()


def update_factory_alpha(factory_id, alpha_value):
    """
    Update a factory's best alpha value after grid search.
    Called during personalization phase.
    """
    db = SessionLocal()
    try:
        factory = db.query(Factory).filter(
            Factory.factory_id == factory_id
        ).first()
        if factory:
            factory.alpha_value = alpha_value
            db.commit()
            print(f"  [DB] Factory {factory_id} alpha={alpha_value} updated")
    except Exception as e:
        print(f"  [DB ERROR] Failed to update alpha: {e}")
        db.rollback()
    finally:
        db.close()

def _broadcast_cluster_event(round_num, factory_id, cluster_id,
                             silhouette_score, k_value):
    """Broadcast cluster assignment event to dashboard."""
    try:
        event = {
            "type":             "cluster_assigned",
            "round_num":        round_num,
            "factory_id":       factory_id,
            "cluster_id":       cluster_id,
            "silhouette_score": round(silhouette_score, 4),
            "k_value":          k_value,
            "timestamp":        datetime.utcnow().isoformat()
        }
        requests.post(
            "http://localhost:8000/ws/broadcast",
            json=event,
            timeout=1
        )
    except Exception:
        pass


def log_round_summary(round_num, clustered_accuracy, naive_global,
                      n_clients, clustering_fired=False):
    """
    One row per round — stores both accuracy metrics for the dashboard.
    Called from aggregate_evaluate after both phases complete.
    Upserts so re-runs don't create duplicate rows.
    """
    db = SessionLocal()
    try:
        existing = db.query(RoundSummary).filter(
            RoundSummary.round_num == round_num
        ).first()
        if existing:
            existing.clustered_accuracy = clustered_accuracy
            existing.naive_global       = naive_global
            existing.n_clients          = n_clients
            existing.clustering_fired   = clustering_fired
            existing.timestamp          = datetime.utcnow()
        else:
            db.add(RoundSummary(
                round_num          = round_num,
                clustered_accuracy = clustered_accuracy,
                naive_global       = naive_global,
                n_clients          = n_clients,
                clustering_fired   = clustering_fired,
                timestamp          = datetime.utcnow()
            ))
        db.commit()

        # Broadcast summary to dashboard
        _broadcast_round_summary(
            round_num, clustered_accuracy, naive_global, clustering_fired
        )

    except Exception as e:
        print(f"  [DB ERROR] Failed to log round summary: {e}")
        db.rollback()
    finally:
        db.close()

def _broadcast_round_summary(round_num, clustered_accuracy, naive_global, clustering_fired):
    """Broadcast both accuracy metrics after evaluate_round completes."""
    try:
        event = {
            "type":               "round_summary",
            "round_num":          round_num,
            "clustered_accuracy": round(clustered_accuracy, 4) if clustered_accuracy else None,
            "naive_global":       round(naive_global, 4) if naive_global else None,
            "clustering_fired":   clustering_fired,
            "timestamp":          datetime.utcnow().isoformat()
        }
        requests.post(
            "http://localhost:8000/ws/broadcast",
            json=event,
            timeout=1
        )
    except Exception:
        pass
