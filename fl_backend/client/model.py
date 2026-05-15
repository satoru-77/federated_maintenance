# model.py
# This is the only file Member 1 needs from Member 2.
# It contains the CNN architecture — nothing else.
# No training code. No data loading. Just the model.

import torch
import torch.nn as nn


class FailureCNN(nn.Module):
    """
    1D Convolutional Neural Network for turbofan engine failure prediction.

    Input shape:  (batch_size, seq_length, n_sensors)
    Output shape: (batch_size, 2)  → [prob_healthy, prob_failing]

    Trained on NASA CMAPSS dataset.
    Used by all 4 factory clients in the Federated Learning system.
    """

    def __init__(self, n_sensors=14, seq_length=30):
        super(FailureCNN, self).__init__()

        self.n_sensors = n_sensors
        self.seq_length = seq_length

        self.conv1   = nn.Conv1d(in_channels=n_sensors, out_channels=32,
                                 kernel_size=3, padding=1)
        self.conv2   = nn.Conv1d(in_channels=32, out_channels=64,
                                 kernel_size=3, padding=1)
        self.relu    = nn.ReLU()
        self.pool    = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(0.3)
        self.fc      = nn.Linear(64, 2)

    def forward(self, x):
        # x: (batch, seq_length, n_sensors)
        x = x.permute(0, 2, 1)          # → (batch, n_sensors, seq_length)
        x = self.relu(self.conv1(x))    # → (batch, 32, seq_length)
        x = self.relu(self.conv2(x))    # → (batch, 64, seq_length)
        x = self.pool(x)                # → (batch, 64, 1)
        x = x.squeeze(-1)              # → (batch, 64)
        x = self.dropout(x)
        x = self.fc(x)                  # → (batch, 2)
        return x


def get_model(n_sensors=14, seq_length=30):
    """
    Factory function — returns a fresh untrained model.
    Called by Flower factory clients on startup.
    """
    return FailureCNN(n_sensors=n_sensors, seq_length=seq_length)


def load_model(weights_path, n_sensors=14, seq_length=30):
    """
    Load a previously trained model from a .pt file.
    Called by SHAP explainer and evaluation scripts.
    """
    model = FailureCNN(n_sensors=n_sensors, seq_length=seq_length)
    model.load_state_dict(torch.load(weights_path, map_location='cpu'))
    model.eval()
    return model


if __name__ == '__main__':
    # Quick sanity check — run this file directly to verify it works
    # python model.py
    model = get_model(n_sensors=14, seq_length=30)
    
    dummy_input = torch.randn(4, 30, 14)  # batch of 4 windows
    output = model(dummy_input)
    
    print("model.py sanity check:")
    print(f"  Input shape:  {dummy_input.shape}")
    print(f"  Output shape: {output.shape}")
    print(f"  Expected:     torch.Size([4, 2])")
    print(f"  Status: {'✅ PASS' if output.shape == torch.Size([4, 2]) else '❌ FAIL'}")