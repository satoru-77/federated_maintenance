# data_loader.py
# Called by Flower factory clients in fl_backend
# Each factory loads its own dataset — never shares raw data

import numpy as np
import pandas as pd
import pickle
from sklearn.preprocessing import MinMaxScaler


# Map factory ID to dataset file
FACTORY_DATASETS = {
    1: 'train_FD001.txt',
    2: 'train_FD002.txt',
    3: 'train_FD003.txt',
    4: 'train_FD004.txt',
}

# Map factory ID to number of useful sensors
# (determined from notebook analysis)
FACTORY_N_SENSORS = {
    1: 14,
    2: 19,
    3: 16,
    4: 19,
}


def load_factory_data(factory_id, data_dir='.', window_size=30):
    """
    Load and prepare data for a specific factory.

    Args:
        factory_id: int, 1-4
        data_dir:   str, path to folder containing .txt files
        window_size: int, sliding window length (default 30)

    Returns:
        X_train, X_val, y_train, y_val  (numpy arrays)
        scaler                           (fitted MinMaxScaler)
        useful_sensors                   (list of sensor column names)
    """
    import os
    from sklearn.model_selection import train_test_split

    filename = os.path.join(data_dir, FACTORY_DATASETS[factory_id])
    print(f"Factory {factory_id}: loading {filename}")

    # ── Load raw data ────────────────────────────────────────────
    col_names = (
        ['engine_id', 'cycle'] +
        ['setting_1', 'setting_2', 'setting_3'] +
        ['sensor_' + str(i) for i in range(1, 22)]
    )
    df = pd.read_csv(filename, sep=r'\s+', header=None)
    df.columns = col_names

    # ── Compute RUL and labels ───────────────────────────────────
    max_cycles = df.groupby('engine_id')['cycle'].max().reset_index()
    max_cycles.columns = ['engine_id', 'max_cycle']
    df = df.merge(max_cycles, on='engine_id')
    df['RUL'] = df['max_cycle'] - df['cycle']
    df['label'] = (df['RUL'] <= 30).astype(int)

    # ── Find useful sensors ──────────────────────────────────────
    sensor_cols = ['sensor_' + str(i) for i in range(1, 22)]
    useful_sensors = [s for s in sensor_cols if df[s].nunique() > 2]
    print(f"Factory {factory_id}: {len(useful_sensors)} useful sensors")

    # ── Normalize ────────────────────────────────────────────────
    scaler = MinMaxScaler()
    df[useful_sensors] = scaler.fit_transform(df[useful_sensors])

    # ── Create sliding windows ───────────────────────────────────
    X, y = _make_windows(df, useful_sensors, window_size)
    print(f"Factory {factory_id}: {X.shape[0]} windows created")

    # ── Train / val split ────────────────────────────────────────
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    return X_train, X_val, y_train, y_val, scaler, useful_sensors


def _make_windows(df, sensor_cols, window_size):
    """Internal — creates sliding windows from dataframe."""
    X, y = [], []
    for eid in df['engine_id'].unique():
        edf = df[df['engine_id'] == eid].sort_values('cycle')
        vals = edf[sensor_cols].values
        labels = edf['label'].values
        for i in range(len(edf) - window_size + 1):
            X.append(vals[i:i + window_size])
            y.append(labels[i + window_size - 1])
    return np.array(X), np.array(y)


if __name__ == '__main__':
    # Quick test — run: python data_loader.py
    for fid in [1, 2, 3, 4]:
        X_tr, X_val, y_tr, y_val, scaler, sensors = load_factory_data(fid, data_dir='.')
        print(f"  Factory {fid}: X_train={X_tr.shape}, "
              f"sensors={len(sensors)}, "
              f"failure_rate={y_tr.mean():.1%}")
        print()