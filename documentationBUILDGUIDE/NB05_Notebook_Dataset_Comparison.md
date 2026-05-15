# NB05 — Notebook: Dataset Comparison Across All 4 Factories

**File:** `machine_learning/notebooks/05_comparison.ipynb`  
**Purpose:** Cross-dataset analysis — compare all 4 factory models side-by-side, motivate why adaptive clustering will improve accuracy, and save results to JSON.  
**Output files:** `comparison_results.json`, `chart_model_comparison.png` (approx)

---

## What This Notebook Does

After training all 4 individual CNN models (NB01–NB04), this notebook:
1. Aggregates the **real measured performance** from each training run
2. Visualizes AUC-ROC scores as a bar chart
3. Creates a scatter plot showing operating conditions vs AUC
4. Argues mathematically why K-means clustering on these factories will work
5. Saves results to JSON for reference

---

## Section 1 — Real Results Dictionary (Cell 1)

The numbers here are **actual measured results** from the 4 training notebooks (not simulated):

```python
results = {
    'Factory 1 (FD001)': {
        'dataset':       'FD001',
        'auc':           0.9704,    # AUC-ROC on val set
        'n_windows':     17731,     # total sliding windows created
        'n_sensors':     14,        # useful sensors after selection
        'op_conditions': 1,
        'fault_modes':   1,
    },
    'Factory 2 (FD002)': {
        'dataset':       'FD002',
        'auc':           0.8925,
        'n_windows':     46123,
        'n_sensors':     19,
        'op_conditions': 6,
        'fault_modes':   1,
    },
    'Factory 3 (FD003)': {
        'dataset':       'FD003',
        'auc':           0.9811,
        'n_windows':     21542,
        'n_sensors':     16,
        'op_conditions': 1,
        'fault_modes':   2,
    },
    'Factory 4 (FD004)': {
        'dataset':       'FD004',
        'auc':           0.9128,
        'n_windows':     54089,
        'n_sensors':     19,
        'op_conditions': 6,
        'fault_modes':   2,
    },
}
```

**Key observation:** Factory 1 (0.9704) and Factory 3 (0.9811) have similar high AUC — both have 1 operating condition. Factory 2 (0.8925) and Factory 4 (0.9128) are lower — both have 6 operating conditions. This pattern directly motivates clustering.

---

## Section 2 — Comparison Table (Cell 2)

```python
import pandas as pd

df = pd.DataFrame(results).T
df = df[['dataset', 'op_conditions', 'fault_modes',
          'n_sensors', 'n_windows', 'auc']]
df.columns = ['Dataset', 'Op Conditions', 'Fault Modes',
              'Useful Sensors', 'Training Windows', 'AUC-ROC']

print(df.to_string())
```

**Printed table:**
```
                    Dataset  Op Conditions  Fault Modes  Useful Sensors  Training Windows  AUC-ROC
Factory 1 (FD001)   FD001              1            1              14             17731   0.9704
Factory 2 (FD002)   FD002              6            1              19             46123   0.8925
Factory 3 (FD003)   FD003              1            2              16             21542   0.9811
Factory 4 (FD004)   FD004              6            2              19             54089   0.9128
```

---

## Section 3 — AUC Bar Chart (Cell 4)

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 5))

factories = list(results.keys())
aucs      = [results[f]['auc'] for f in factories]
colors    = ['#378ADD', '#D85A30', '#1D9E75', '#7F77DD']
# Blue=Mumbai, Orange=Berlin, Green=Detroit, Purple=Tokyo

bars = ax.bar(factories, aucs, color=colors, width=0.5, edgecolor='black', linewidth=0.7)

# Annotate each bar with its AUC value
for bar, auc in zip(bars, aucs):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 0.002,
        f'{auc:.4f}',
        ha='center', va='bottom', fontsize=10, fontweight='bold'
    )

ax.set_ylim(0.85, 1.0)
ax.set_ylabel('AUC-ROC Score')
ax.set_title('Per-Factory CNN Model Performance (Individual Training)')
ax.axhline(y=0.9, color='red', linestyle='--', alpha=0.5, label='0.90 threshold')
plt.tight_layout()
plt.savefig('chart_auc_comparison.png', dpi=150, bbox_inches='tight')
plt.show()
```

**Chart interpretation:**
- Factories 1 & 3 (1 op condition) cluster above 0.97
- Factories 2 & 4 (6 op conditions) cluster around 0.89–0.91
- Clear performance split driven by operating condition complexity

---

## Section 4 — Operating Conditions vs AUC Scatter (Cell 6)

```python
fig, ax = plt.subplots(figsize=(7, 5))

for name, r in results.items():
    ax.scatter(r['op_conditions'], r['auc'], s=200, zorder=5, label=name)
    ax.annotate(
        r['dataset'],
        (r['op_conditions'], r['auc']),
        textcoords="offset points", xytext=(8, 4), fontsize=9
    )

ax.set_xlabel('Number of Operating Conditions')
ax.set_ylabel('AUC-ROC Score')
ax.set_title('Operating Conditions vs Model Performance')
ax.set_xticks([1, 6])
ax.legend(loc='lower right', fontsize=8)
plt.tight_layout()
plt.savefig('chart_operating_conditions.png', dpi=150)
```

**Result:** Clear negative correlation — more operating conditions = lower AUC. This is the mathematical motivation for clustering: group factories by operating-condition complexity so they can share appropriate gradient updates.

---

## Section 5 — Why Clustering Will Work (Cell 8)

```python
print("=" * 60)
print("WHY ADAPTIVE CLUSTERING WILL HELP")
print("=" * 60)

print("\nCLUSTER A (predicted):")
print("  Factory 1 (FD001) — 1 op condition, AUC 0.9704")
print("  Factory 3 (FD003) — 1 op condition, AUC 0.9811")
print("  → Similar gradient directions during training")
print("  → Sharing weights between them should IMPROVE both")

print("\nCLUSTER B (predicted):")
print("  Factory 2 (FD002) — 6 op conditions, AUC 0.8925")
print("  Factory 4 (FD004) — 6 op conditions, AUC 0.9128")
print("  → Both learned to handle multi-condition complexity")
print("  → Sharing weights between them should improve robustness")

print("\nWHY CROSS-CLUSTER SHARING HURTS:")
print("  Factory 1's weights: tuned for 1 condition → 14 sensors")
print("  Factory 2's weights: tuned for 6 conditions → 19 sensors")
print("  → Different sensor sets, different conv1 weight shapes (conceptually)")
print("  → FedAvg across all 4 would dilute both — clustering fixes this")
```

**Academic argument:**  
After 10 rounds of global FedAvg, the K-means clustering algorithm runs on the **weight gradients** (not the weights themselves). The gradient similarity is high within same-condition-complexity groups (FD001/FD003 vs FD002/FD004) because:
- Similar loss surfaces → similar gradient directions
- Different condition complexity → different gradient magnitudes
- K-means on normalized gradients naturally separates the two groups

---

## Section 6 — Save Results to JSON (Cell 10)

```python
import json

comparison = {
    'FD001': {'auc': 0.9704, 'op_conditions': 1, 'fault_modes': 1},
    'FD002': {'auc': 0.8925, 'op_conditions': 6, 'fault_modes': 1},
    'FD003': {'auc': 0.9811, 'op_conditions': 1, 'fault_modes': 2},
    'FD004': {'auc': 0.9128, 'op_conditions': 6, 'fault_modes': 2},
}

with open('comparison_results.json', 'w') as f:
    json.dump(comparison, f, indent=2)

print("Saved → comparison_results.json")
```

**Output file `comparison_results.json`:**
```json
{
  "FD001": {"auc": 0.9704, "op_conditions": 1, "fault_modes": 1},
  "FD002": {"auc": 0.8925, "op_conditions": 6, "fault_modes": 1},
  "FD003": {"auc": 0.9811, "op_conditions": 1, "fault_modes": 2},
  "FD004": {"auc": 0.9128, "op_conditions": 6, "fault_modes": 2}
}
```

This file is read by the Django `overview` view to display the pre-training accuracy baseline in the dashboard.

---

## Key Conclusions from This Notebook

```
1. AUC gap between 1-condition (FD001/FD003 ≈ 0.97) 
   and 6-condition (FD002/FD004 ≈ 0.90) factories is ~7%

2. This gap is NOT due to fault modes (FD003 with 2 faults scores 0.98)
   → Operating conditions are the primary difficulty driver

3. Predicted clustering: {FD001, FD003} in Cluster A, {FD002, FD004} in Cluster B
   → Confirmed by notebook 06 and the live FL system

4. Sharing weights within clusters is beneficial
   Sharing weights across clusters dilutes specialized representations

5. The federated approach after clustering should:
   → Maintain FD001/FD003 performance above 0.96
   → Improve FD002/FD004 performance toward 0.94+
```
