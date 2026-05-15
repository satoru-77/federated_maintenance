import pickle
for i in range(1, 5):
    try:
        with open(f"useful_sensors_FD00{i}.pkl", "rb") as f:
            s = pickle.load(f)
            print(f"Factory {i}: {len(s)} sensors -> {s}")
    except Exception as e:
        print(f"Factory {i}: {e}")
