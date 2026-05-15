import torch
import torch.nn as nn

class FailureCNN(nn.Module):
    def __init__(self, n_sensors=14):
        super().__init__()
        self.conv1   = nn.Conv1d(n_sensors, 32, kernel_size=3, padding=1)
        self.conv2   = nn.Conv1d(32, 64, kernel_size=3, padding=1)
        self.relu    = nn.ReLU()
        self.pool    = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(0.3)
        self.fc      = nn.Linear(64, 2)

    def forward(self, x):
        x = x.permute(0, 2, 1)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        x = self.pool(x).squeeze(-1)
        x = self.dropout(x)
        return self.fc(x)

configs = {
    1: 14,
    2: 19,
    3: 16,
    4: 20,
}

for fid, n in configs.items():
    sd = torch.load(f'best_model_FD00{fid}.pt', map_location='cpu', weights_only=True)
    m = FailureCNN(n_sensors=n)
    m.load_state_dict(sd)
    m.eval()
    total_params = sum(p.numel() for p in m.parameters())
    print(f"=== Factory {fid} — FD00{fid} ===")
    print(f"  Total trainable params : {total_params:,}")
    print(f"  conv1.weight shape     : {list(sd['conv1.weight'].shape)}  (Conv1D: {n} sensors -> 32 filters, kernel=3)")
    print(f"  conv2.weight shape     : {list(sd['conv2.weight'].shape)}  (Conv1D: 32 -> 64 filters, kernel=3)")
    print(f"  fc.weight shape        : {list(sd['fc.weight'].shape)}      (Linear: 64 -> 2 classes)")
    # Prove real forward pass
    x = torch.randn(1, 30, n)
    with torch.no_grad():
        out = m(x)
        probs = torch.softmax(out, dim=1)[0]
    print(f"  Forward pass output    : HEALTHY={probs[0].item():.4f}, FAILURE={probs[1].item():.4f}")
    print()
