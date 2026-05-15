# run_personalization.py
# Run this AFTER the FL system finishes
# python run_personalization.py

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from client.model import FailureCNN
from client.data_loader import load_factory_data
from backend.db import SessionLocal
from backend.models import Factory, ClusterAssignment
from server.personalization import PersonalizationManager
import numpy as np
import gc

def run():
    db = SessionLocal()
    
    # Get cluster assignments from DB
    factories = db.query(Factory).all()
    assignments = {f.factory_id: f.cluster_id for f in factories}
    
    print("Cluster assignments from DB:")
    for fid, cid in assignments.items():
        print(f"  Factory {fid} → Cluster {cid}")
    
    if all(v is None for v in assignments.values()):
        print("ERROR: No cluster assignments found. Run FL first.")
        return

    # We need cluster model weights — load from saved files
    # For now use equal blend (alpha=0.5) as baseline
    # and find best alpha per factory
    
    manager = PersonalizationManager()
    
    for factory_id in [1, 2, 3, 4]:
        cluster_id = assignments.get(factory_id)
        if cluster_id is None:
            print(f"Factory {factory_id} has no cluster — skipping")
            continue
        
        print(f"\nProcessing Factory {factory_id} (Cluster {cluster_id})...")
        
        # Load this factory's data
        _, X_val, _, y_val, _, _ = load_factory_data(
            factory_id, data_dir='./client'
        )
        
        # Limit to 1000 samples for memory
        X_val = X_val[:1000]
        y_val = y_val[:1000]
        
        # Create model
        model = FailureCNN(n_sensors=14, seq_length=30)
        
        # Get current weights as both cluster and local
        # (in a real run these would be different — 
        #  for now we demonstrate the alpha search mechanism)
        current_weights = [
            v.cpu().numpy() if hasattr(v, 'cpu') 
            else v
            for v in model.state_dict().values()
        ]
        
        manager.run_personalization(
            factory_id      = factory_id,
            cluster_weights = current_weights,
            local_weights   = current_weights,
            model           = model,
            X_val           = X_val,
            y_val           = y_val
        )
        
        # Clear memory
        del model, X_val, y_val, current_weights
        gc.collect()
    
    manager.get_summary()
    db.close()
    print("\nPersonalization complete!")
    print("Check http://localhost:8000/factories for alpha values")

if __name__ == '__main__':
    run()