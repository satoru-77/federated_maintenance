# models.py
# Defines what our PostgreSQL tables look like using SQLAlchemy
# SQLAlchemy lets us work with the database using Python objects
# instead of writing raw SQL

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, Text, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

# Base is the parent class all our table classes inherit from
Base = declarative_base()


class Factory(Base):
    """
    One row per factory.
    Stores static info + current status.
    """
    __tablename__ = 'factories'

    id          = Column(Integer, primary_key=True)
    factory_id  = Column(Integer, unique=True, nullable=False)
    name        = Column(String(100), nullable=False)
    dataset     = Column(String(10), nullable=False)   # FD001, FD002 etc
    n_engines   = Column(Integer, nullable=False)
    cluster_id  = Column(Integer, nullable=True)       # NULL until clustering
    alpha_value = Column(Float,   nullable=True)       # NULL until personalization
    status      = Column(String(20), default='active') # active/disconnected
    created_at  = Column(DateTime, default=datetime.utcnow)

    # relationship: one factory has many training rounds
    rounds = relationship('TrainingRound', back_populates='factory')


class TrainingRound(Base):
    """
    One row per factory per FL round.
    This is what the dashboard charts.
    """
    __tablename__ = 'training_rounds'

    id          = Column(Integer, primary_key=True)
    round_num   = Column(Integer, nullable=False)
    factory_id  = Column(Integer, ForeignKey('factories.factory_id'))
    algorithm   = Column(String(20), nullable=False)   # FedAvg, FedProx
    accuracy    = Column(Float, nullable=False)
    loss        = Column(Float, nullable=False)
    n_samples   = Column(Integer, nullable=False)
    cluster_id  = Column(Integer, nullable=True)
    timestamp   = Column(DateTime, default=datetime.utcnow)

    factory = relationship('Factory', back_populates='rounds')


class ClusterAssignment(Base):
    """
    One row every time clustering fires or a factory changes cluster.
    Tracks the full history of cluster assignments.
    """
    __tablename__ = 'cluster_assignments'

    id               = Column(Integer, primary_key=True)
    round_num        = Column(Integer, nullable=False)
    factory_id       = Column(Integer, ForeignKey('factories.factory_id'))
    cluster_id       = Column(Integer, nullable=False)
    silhouette_score = Column(Float, nullable=True)
    k_value          = Column(Integer, nullable=False)
    reason           = Column(String(50), default='plateau_detected')
    timestamp        = Column(DateTime, default=datetime.utcnow)


class ModelWeight(Base):
    """
    One row every time we save a model checkpoint.
    Stores the file path, not the actual weights (too large for DB).
    """
    __tablename__ = 'model_weights'

    id           = Column(Integer, primary_key=True)
    round_num    = Column(Integer, nullable=False)
    cluster_id   = Column(Integer, nullable=True)   # NULL = global model
    algorithm    = Column(String(20), nullable=False)
    weights_path = Column(String(200), nullable=False)
    accuracy     = Column(Float, nullable=False)
    timestamp    = Column(DateTime, default=datetime.utcnow)


class Experiment(Base):
    """
    One row per full FL run.
    Tracks which configuration produced which results.
    """
    __tablename__ = 'experiments'

    id                   = Column(Integer, primary_key=True)
    run_id               = Column(String(50), unique=True, nullable=False)
    strategy             = Column(String(20), nullable=False)
    k_value              = Column(Integer, nullable=False)
    alpha_mode           = Column(String(20), nullable=False)
    dp_on                = Column(Boolean, default=False)
    global_accuracy      = Column(Float, nullable=True)
    best_cluster_accuracy= Column(Float, nullable=True)
    notes                = Column(Text, nullable=True)
    timestamp            = Column(DateTime, default=datetime.utcnow)


class RoundSummary(Base):
    """
    One row per FL round — stores both accuracy metrics.
    clustered_accuracy : weighted avg of local training accuracies (fit phase)
    naive_global       : Flower's evaluate_round weighted avg (global model tested on clients)
    These are the two numbers shown side-by-side on the dashboard.
    """
    __tablename__ = 'round_summaries'

    id                 = Column(Integer, primary_key=True)
    round_num          = Column(Integer, nullable=False, unique=True)
    clustered_accuracy = Column(Float, nullable=True)   # from aggregate_fit
    naive_global       = Column(Float, nullable=True)   # from aggregate_evaluate
    n_clients          = Column(Integer, nullable=True)
    clustering_fired   = Column(Boolean, default=False)
    timestamp          = Column(DateTime, default=datetime.utcnow)