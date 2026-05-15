"""Test the full startup sequence of shap_api without starting the server."""
import sys
sys.path.insert(0, '.')

# Simulate what load_models() does
import numpy as np, torch, torch.nn as nn, pickle

ALL_SENSORS = ['sensor_'+str(i) for i in range(1,22)]
FACTORY_CONFIG = {
    1: {'model':'best_model_FD001.pt', 'scaler':'scaler_FD001.pkl', 'data':'train_FD001.txt', 'n_sensors':14, 'name':'Factory Mumbai'},
    2: {'model':'best_model_FD002.pt', 'scaler':'scaler_FD002.pkl', 'data':'train_FD002.txt', 'n_sensors':19, 'name':'Factory Berlin'},
    3: {'model':'best_model_FD003.pt', 'scaler':'scaler_FD003.pkl', 'data':'train_FD003.txt', 'n_sensors':16, 'name':'Factory Detroit'},
    4: {'model':'best_model_FD004.pt', 'scaler':'scaler_FD004.pkl', 'data':'train_FD004.txt', 'n_sensors':19, 'name':'Factory Tokyo'},
}

class FailureCNN(nn.Module):
    def __init__(self, n=14):
        super().__init__()
        self.conv1=nn.Conv1d(n,32,3,padding=1); self.conv2=nn.Conv1d(32,64,3,padding=1)
        self.relu=nn.ReLU(); self.pool=nn.AdaptiveAvgPool1d(1)
        self.dropout=nn.Dropout(0.3); self.fc=nn.Linear(64,2)
    def forward(self,x):
        x=x.permute(0,2,1); x=self.relu(self.conv1(x)); x=self.relu(self.conv2(x))
        return self.fc(self.dropout(self.pool(x).squeeze(-1)))

def load_bg(filename, n_sensors=14):
    import pandas as pd
    from sklearn.preprocessing import MinMaxScaler
    col_names = ['engine_id','cycle','s1','s2','s3']+ALL_SENSORS
    df = pd.read_csv(filename, sep=r'\s+', header=None, nrows=3000)
    df.columns = col_names
    sensor_cols = ALL_SENSORS[:n_sensors]
    scaler = MinMaxScaler()
    df[sensor_cols] = scaler.fit_transform(df[sensor_cols]).astype(np.float32)
    windows = []
    for eid in list(df['engine_id'].unique())[:5]:
        edf = df[df['engine_id']==eid].sort_values('cycle')
        vals = edf[sensor_cols].values
        if len(vals)>=30: windows.append(vals[:30])
        if len(windows)>=5: break
    if not windows: windows=[np.random.rand(30,n_sensors).astype(np.float32)]
    return np.array(windows, dtype=np.float32)

for fid, cfg in FACTORY_CONFIG.items():
    try:
        n = cfg['n_sensors']
        m = FailureCNN(n)
        m.load_state_dict(torch.load(cfg['model'], map_location='cpu', weights_only=True))
        m.eval()
        print(f"F{fid} model: OK")
    except Exception as e:
        print(f"F{fid} model FAIL: {e}"); continue
    try:
        with open(cfg['scaler'],'rb') as f: pickle.load(f)
        print(f"F{fid} scaler: OK")
    except Exception as e:
        print(f"F{fid} scaler FAIL: {e}")
    try:
        bg = load_bg(cfg['data'], n_sensors=n)
        print(f"F{fid} bg data: OK shape={bg.shape}")
    except Exception as e:
        print(f"F{fid} bg FAIL: {e}")
    print()
