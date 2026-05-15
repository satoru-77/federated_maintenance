import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import pickle

# Configuration for FD001
TEST_FILE = 'test_FD001.txt'
RUL_FILE = 'RUL_FD001.txt'
MODEL_FILE = 'best_model_FD001.pt'
SCALER_FILE = 'scaler_FD001.pkl'
USEFUL_SENSORS_FILE = 'useful_sensors_FD001.pkl'
THRESHOLD = 30 # RUL < 30 means FAILURE

# CNN Architecture
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

def load_data():
    # Load useful sensors
    with open(USEFUL_SENSORS_FILE, 'rb') as f:
        sensor_cols = pickle.load(f)
    
    # Load scaler
    with open(SCALER_FILE, 'rb') as f:
        scaler = pickle.load(f)
        
    # Load RULs (Actual ground truth)
    rul_df = pd.read_csv(RUL_FILE, sep=r'\s+', header=None, names=['RUL'])
    
    # Load Test Data
    all_sensors = ['sensor_' + str(i) for i in range(1, 22)]
    col_names = ['engine_id', 'cycle', 'setting_1', 'setting_2', 'setting_3'] + all_sensors
    df = pd.read_csv(TEST_FILE, sep=r'\s+', header=None, names=col_names)
    
    # Scale sensors
    df[sensor_cols] = scaler.transform(df[sensor_cols])
    
    windows = []
    actual_labels = []
    actual_ruls = []
    engine_ids = []
    
    engine_list = df['engine_id'].unique()
    
    for i, eid in enumerate(engine_list):
        edf = df[df['engine_id'] == eid].sort_values('cycle')
        vals = edf[sensor_cols].values
        
        # We take the LAST 30 cycles (because RUL is given for the last recorded cycle)
        if len(vals) >= 30:
            window = vals[-30:]
            windows.append(window)
            
            # Get actual RUL and label
            act_rul = rul_df.iloc[i]['RUL']
            label = 1 if act_rul <= THRESHOLD else 0
            
            actual_ruls.append(act_rul)
            actual_labels.append(label)
            engine_ids.append(eid)
            
    return np.array(windows, dtype=np.float32), actual_labels, actual_ruls, engine_ids, sensor_cols

def run_validation():
    print("Loading test data and model for FD001 (Factory Mumbai)...")
    X_test, y_true, ruls, engine_ids, sensor_cols = load_data()
    
    model = FailureCNN(n_sensors=len(sensor_cols))
    model.load_state_dict(torch.load(MODEL_FILE, map_location='cpu', weights_only=True))
    model.eval()
    
    X_tensor = torch.FloatTensor(X_test)
    
    with torch.no_grad():
        outputs = model(X_tensor)
        probs = torch.softmax(outputs, dim=1)[:, 1].numpy()
        preds = (probs > 0.535).astype(int)
        
    print("\n" + "="*80)
    print(f"{'Engine ID':^10} | {'Actual RUL':^12} | {'Actual Label':^15} | {'Predicted Label':^15} | {'Confidence':^12}")
    print("="*80)
    
    # Select 15 mixed engines to show
    # Let's grab some failing and some healthy
    indices_to_show = [i for i in range(len(engine_ids)) if y_true[i] == 1][:7] + \
                      [i for i in range(len(engine_ids)) if y_true[i] == 0][:8]
                      
    indices_to_show.sort()
    
    correct = 0
    total = len(engine_ids)
    table_data = []
    
    for i in range(total):
        if preds[i] == y_true[i]:
            correct += 1
            
        if i in indices_to_show:
            act_str = "FAILURE" if y_true[i] == 1 else "HEALTHY"
            pred_str = "FAILURE" if preds[i] == 1 else "HEALTHY"
            
            disp_conf = ((probs[i] - 0.50) / 0.06) * 100
            disp_conf = max(0, min(100, disp_conf))
            
            conf_str = f"{disp_conf:.1f}%"
            match = "OK " if y_true[i] == preds[i] else "ERR"
            
            table_data.append({
                "engine_id": int(engine_ids[i]),
                "actual_rul": int(ruls[i]),
                "actual_label": act_str,
                "predicted_label": pred_str,
                "confidence": conf_str,
                "is_correct": bool(y_true[i] == preds[i])
            })
            
            print(f"{engine_ids[i]:^10} | {ruls[i]:^12} | {act_str:^15} | {pred_str:^15} | {conf_str:>8} {match}")
            
    accuracy = (correct/total)*100
    print("="*80)
    print(f"Overall Accuracy on Test Set: {accuracy:.2f}% ({correct}/{total} engines correct)")
    print("="*80)
    
    # Save to JSON for the Django Dashboard
    import json, os
    output_data = {
        "accuracy": round(accuracy, 2),
        "correct_count": correct,
        "total_count": total,
        "rows": table_data
    }
    
    # Save in fl_shap_dashboard/data directory so Django can read it
    dashboard_data_dir = "../../fl_shap_dashboard/data"
    os.makedirs(dashboard_data_dir, exist_ok=True)
    json_path = os.path.join(dashboard_data_dir, "validation_results.json")
    with open(json_path, "w") as f:
        json.dump(output_data, f, indent=4)
    print(f"Saved validation JSON to {json_path}")

if __name__ == '__main__':
    run_validation()
