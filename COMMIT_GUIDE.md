# FedPredict — Collaborative Commit Guide (Today)

> **Situation:** 3 contributors, 1 shared GitHub repo. Each person owns a folder.
> You (Indra) push today. Friends push their own folders later from their own machines.

---

## Who Owns What

| Contributor | Folder | Pushes |
|-------------|--------|--------|
| **You (Indra)** | `fl_backend/`, `documentationBUILDGUIDE/`, `start_all.ps1` | Today |
| **ML Friend** | `machine_learning/` | Later, from their machine |
| **Dashboard Friend** | `fl_shap_dashboard/` | Later, from their machine |

The `.gitignore` already **excludes** `machine_learning/` and `fl_shap_dashboard/` from your commits — so you won't accidentally push their files, and they won't conflict when they push.

---

## Step 1 — Prepare Your Machine

```powershell
cd d:\PROJECTS\Federated_Maintenance

# Confirm .gitignore is working — these should NOT appear:
git status
# You should NOT see machine_learning/ or fl_shap_dashboard/ listed
# You SHOULD see fl_backend/, documentationBUILDGUIDE/, start_all.ps1, .gitignore
```

---

## Step 2 — Reset the Old "All-At-Once" Commit

You currently have 1 commit that dumped everything. Let's undo it cleanly.

```powershell
# Undo the commit but keep all your files unchanged
git update-ref -d HEAD

# Unstage everything
git rm -rf --cached .

# Confirm clean state (all files appear as untracked)
git status
```

---

## Step 3 — Stage & Commit Your Files

Now add only YOUR files:

```powershell
# Core FL backend
git add fl_backend/

# Startup script
git add start_all.ps1

# Gitignore itself
git add .gitignore

# Documentation guide
git add documentationBUILDGUIDE/

# Check what's staged
git status
```

> ⚠️ Make sure `machine_learning/` and `fl_shap_dashboard/` are **NOT** in the staged list. If they are, the `.gitignore` wasn't applied — run `git rm -rf --cached machine_learning/ fl_shap_dashboard/` to remove them.

---

## Step 4 — Commit

```powershell
git commit -m "feat: add FL backend, server strategy, clustering, security, and build docs"
```

---

## Step 5 — Force Push to GitHub (to overwrite old history)

```powershell
git push origin main --force
```

> `--force` is needed because the old commit history is being replaced. This is fine — only you have been using this repo so far.

---

## Step 6 — Verify on GitHub

Go to your GitHub repo. You should see:
- ✅ `fl_backend/` folder
- ✅ `documentationBUILDGUIDE/` folder
- ✅ `start_all.ps1`
- ✅ `.gitignore`
- ❌ `machine_learning/` — NOT visible (gitignored)
- ❌ `fl_shap_dashboard/` — NOT visible (gitignored)

---

## What Your Friends Do (On Their Machines)

### ML Friend

```bash
# Clone the repo
git clone https://github.com/your-username/Federated_Maintenance.git
cd Federated_Maintenance

# They already have their machine_learning/ folder locally
# They need to REMOVE machine_learning/ from .gitignore first
# Edit .gitignore: comment out or delete the line: machine_learning/

# Then stage and push their folder
git add machine_learning/
git add .gitignore   # updated to track their folder
git commit -m "feat(ml): add CNN1D notebooks, SHAP analysis, FL vs centralized experiments"
git push origin main
```

### Dashboard Friend

```bash
git clone https://github.com/your-username/Federated_Maintenance.git
cd Federated_Maintenance

# Edit .gitignore: remove the line: fl_shap_dashboard/
git add fl_shap_dashboard/
git add .gitignore
git commit -m "feat(dashboard): add Django dashboard, D3 charts, SHAP explainability page"
git push origin main
```

---

## Alternative: Per-Person `.gitignore` Approach (Cleaner)

Instead of editing the shared `.gitignore`, each friend can use their **own local ignore**:

```bash
# On ML friend's machine (doesn't touch shared .gitignore):
echo "fl_shap_dashboard/" >> .git/info/exclude
echo "fl_backend/" >> .git/info/exclude

# This is local only — never pushed to GitHub
# Now they can freely add machine_learning/ without conflict
git add machine_learning/
git commit -m "feat(ml): ..."
git push origin main
```

---

## Final Repo Structure on GitHub (After All 3 Push)

```
Federated_Maintenance/
├── .gitignore
├── start_all.ps1
├── fl_backend/              ← Indra
│   ├── server/
│   ├── client/
│   └── backend/
├── documentationBUILDGUIDE/ ← Indra
│   ├── README.md
│   ├── 01_System_Architecture_Overview.md
│   └── ... (44 docs)
├── machine_learning/        ← ML Friend
│   └── notebooks/
└── fl_shap_dashboard/       ← Dashboard Friend
    ├── templates/
    └── dashboard/
```

---

## Quick Checklist

- [ ] `.gitignore` has `machine_learning/` and `fl_shap_dashboard/` listed
- [ ] `git status` does NOT show those folders
- [ ] `git update-ref -d HEAD` run to undo old commit
- [ ] `git rm -rf --cached .` run to unstage everything
- [ ] Only `fl_backend/`, `documentationBUILDGUIDE/`, `start_all.ps1`, `.gitignore` staged
- [ ] `git push origin main --force` done
- [ ] Friends added as **collaborators** on GitHub (Settings → Collaborators)
