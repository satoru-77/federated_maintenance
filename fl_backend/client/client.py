# client.py
# One Flower client = one factory
# Run 4 times with different --factory-id arguments
#
# Usage:
#   python -m client.client --factory-id 1
#   python -m client.client --factory-id 2
#   python -m client.client --factory-id 3
#   python -m client.client --factory-id 4

import argparse
import torch
import torch.nn as nn
import numpy as np
import flwr as fl
from collections import OrderedDict

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server.security import DifferentialPrivacy

from .model import FailureCNN
from .data_loader import load_factory_data

# Path to data files relative to this client folder
DATA_DIR = "./client"

# Map factory_id to number of sensors
# (matches what data_loader.py found in notebooks)
FACTORY_SENSORS = {1: 14, 2: 19, 3: 16, 4: 19}


class FactoryClient(fl.client.NumPyClient):
    """
    One instance of this class runs on each factory.

    Flower calls these methods:
      get_parameters() → send current model weights to server
      fit()            → train locally, send updated weights
      evaluate()       → test on validation data, send metrics
    """

    def __init__(self, factory_id):
        self.factory_id = factory_id
        self.n_sensors  = FACTORY_SENSORS[factory_id]

        print(f"\n[Factory {factory_id}] Loading data...")

        # Load this factory's dataset
        (self.X_train, self.X_val,
         self.y_train, self.y_val,
         self.scaler, self.sensors) = load_factory_data(
            factory_id, data_dir=DATA_DIR
        )

        self.n_sensors = len(self.sensors)
        print(f"[Factory {factory_id}] "
              f"Train={self.X_train.shape[0]} windows, "
              f"Val={self.X_val.shape[0]} windows, "
              f"Sensors={self.n_sensors}")

        # Create the model
        self.model = FailureCNN(
            n_sensors  = self.n_sensors,
            seq_length = 30
        )

        # Loss function — weight failures 5x more
        self.criterion = nn.CrossEntropyLoss(
            weight=torch.tensor([1.0, 5.0])
        )
        self.optimizer = torch.optim.Adam(
            self.model.parameters(), lr=0.001
        )

        # Convert data to tensors once (saves time per round)
        self.X_train_t = torch.FloatTensor(self.X_train)
        self.y_train_t = torch.LongTensor(self.y_train)
        self.X_val_t   = torch.FloatTensor(self.X_val)
        self.y_val_t   = torch.LongTensor(self.y_val)

        # Differential Privacy
        self.dp = DifferentialPrivacy(
            epsilon     = 1.0,
            delta       = 1e-5,
            sensitivity = 0.001
        )
        print(f"[Factory {factory_id}] DP enabled (epsilon=1.0)")
        print(f"[Factory {factory_id}] Ready [OK]")


    def get_parameters(self, config):
        """
        Return model weights with differential privacy noise added.
        The noise prevents reconstruction of raw sensor data.
        """
        raw_weights = [
            val.cpu().numpy()
            for val in self.model.state_dict().values()
        ]
        
        # --- BYZANTINE ATTACK INJECTION ---
        if os.path.exists("byzantine_flag.txt"):
            try:
                with open("byzantine_flag.txt", "r") as f:
                    rogue_id = f.read().strip()
                if str(self.factory_id) == rogue_id:
                    print(f"\n[Factory {self.factory_id}] ⚠️ BYZANTINE ATTACK INITIATED: Sending corrupted weights!")
                    raw_weights = [w * 500 + 100 for w in raw_weights]
                    # Delete the flag so it only fires once
                    os.remove("byzantine_flag.txt")
            except Exception:
                pass

        return self.dp.add_noise(raw_weights)

    def set_parameters(self, parameters):
        """
        Load weights received from the server into local model.
        Called at the start of each round before local training.
        """
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict  = OrderedDict(
            {k: torch.tensor(v) for k, v in params_dict}
        )
        self.model.load_state_dict(state_dict, strict=True)

    def fit(self, parameters, config):
        self.set_parameters(parameters)
        local_epochs = config.get("local_epochs", 5)

        self.model.train()
        for epoch in range(local_epochs):
            self.optimizer.zero_grad()
            outputs = self.model(self.X_train_t)
            loss = self.criterion(outputs, self.y_train_t)
            loss.backward()
            self.optimizer.step()

        # compute accuracy on validation set
        self.model.eval()
        with torch.no_grad():
            val_out = self.model(self.X_val_t)
            probs = torch.softmax(val_out, dim=1)[:, 1].numpy()
            preds = (probs > 0.4).astype(int)
            accuracy = float((preds == self.y_val).mean())

        print(f"  [Factory {self.factory_id}] "
            f"Trained {local_epochs} epochs | "
            f"Loss={loss.item():.4f} | Acc={accuracy:.4f}")

        return self.get_parameters(config={}), len(self.X_train), {
            "factory_id": float(self.factory_id),
            "loss":       float(loss.item()),
            "accuracy":   float(accuracy)
        }
    
    def get_local_weights(self):
        """
        Return current local model weights.
        Called by personalization manager for alpha grid search.
        """
        return [
            val.cpu().numpy()
            for val in self.model.state_dict().values()
        ]

    def get_validation_data(self):
        """
        Return validation data for alpha evaluation.
        """
        return self.X_val, self.y_val

    def evaluate(self, parameters, config):
        """
        Receive global model → evaluate on validation data → report metrics.

        Called by server to measure global model performance.
        """
        self.set_parameters(parameters)
        self.model.eval()

        with torch.no_grad():
            outputs = self.model(self.X_val_t)
            loss    = self.criterion(outputs, self.y_val_t)
            probs   = torch.softmax(outputs, dim=1)[:, 1].numpy()
            preds   = (probs > 0.4).astype(int)

        accuracy = float((preds == self.y_val).mean())

        print(f"  [Factory {self.factory_id}] "
              f"Val accuracy={accuracy:.4f} | "
              f"Loss={loss.item():.4f}")

        return float(loss.item()), len(self.X_val), {"accuracy": accuracy}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--factory-id", type=int, required=True,
        choices=[1, 2, 3, 4],
        help="Which factory this client represents (1-4)"
    )
    parser.add_argument(
        "--server-address", type=str, default="localhost:8080",
        help="Flower server address"
    )
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"Starting Factory {args.factory_id} client")
    print(f"Connecting to server: {args.server_address}")
    print(f"{'='*50}")

    client = FactoryClient(factory_id=args.factory_id)

    fl.client.start_numpy_client(
        server_address=args.server_address,
        client=client
    )


if __name__ == "__main__":
    main()