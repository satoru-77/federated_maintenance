import sys, torch, torch.nn as nn

class FailureCNN(nn.Module):
    def __init__(self, n=14):
        super().__init__()
        self.conv1   = nn.Conv1d(n, 32, 3, padding=1)
        self.conv2   = nn.Conv1d(32, 64, 3, padding=1)
        self.relu    = nn.ReLU()
        self.pool    = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(0.3)
        self.fc      = nn.Linear(64, 2)
    def forward(self, x):
        x = x.permute(0,2,1)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        return self.fc(self.dropout(self.pool(x).squeeze(-1)))

configs = {
    1: ('best_model_FD001.pt', 14),
    2: ('best_model_FD002.pt', 19),
    3: ('best_model_FD003.pt', 16),
    4: ('best_model_FD004.pt', 19),
}

for fid, (mfile, n) in configs.items():
    try:
        sd = torch.load(mfile, map_location='cpu', weights_only=True)
        # Check actual conv1 input channels from saved weights
        actual_n = sd['conv1.weight'].shape[1]
        print(f"Factory {fid}: file says {n} sensors, model has {actual_n} — ", end="")
        m = FailureCNN(actual_n)
        m.load_state_dict(sd)
        print("OK")
    except Exception as e:
        print(f"FAIL: {e}")
