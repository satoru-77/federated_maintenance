## Run notebooks 01-04 to generate model weights

# FL Predictive Maintenance — ML Research

## What this is
Machine learning models and research notebooks for NASA CMAPSS
turbofan engine failure prediction.

## Notebooks (run in order)
01_fd001.ipynb     — EDA + CNN training on FD001
02_fd002.ipynb     — CNN training on FD002
03_fd003.ipynb     — CNN training on FD003
04_fd004.ipynb     — CNN training on FD004
05_comparison.ipynb — AUC comparison across factories
06_noniid.ipynb    — Non-IID distribution analysis
notebook_03...     — 3 model architectures comparison
notebook_04...     — Centralized vs Federated study

## Deliverables
model.py        — CNN architecture (used by Member 1)
data_loader.py  — Data pipeline (used by Member 1)
shap_api.py     — SHAP explainability API on port 8001