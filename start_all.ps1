# start_all.ps1
# Starts the complete Federated Predictive Maintenance System

Write-Host "Starting the complete Federated Learning System..." -ForegroundColor Green

# 1. Start the FastAPI Database Backend (Port 8000)
Write-Host "Launching FastAPI backend..." -ForegroundColor Yellow
$backendPath = Join-Path -Path $PWD -ChildPath "fl_backend"
Set-Location -Path $backendPath
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; venv\Scripts\activate; uvicorn backend.main:app --reload --port 8000"

# 2. Start the SHAP Explainability API (Port 8001)
Write-Host "Launching SHAP Explainability API..." -ForegroundColor Yellow
$shapPath = Join-Path -Path $PSScriptRoot -ChildPath "machine_learning\notebooks"
$shapVenvPath = Join-Path -Path $PSScriptRoot -ChildPath "machine_learning\venv\Scripts\activate.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$shapPath'; . '$shapVenvPath'; python shap_api.py"

# 3. Start the Django Dashboard (Port 8002)
Write-Host "Launching the dashboard frontend..." -ForegroundColor Yellow
$dashboardPath = Join-Path -Path $PSScriptRoot -ChildPath "fl_shap_dashboard"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$dashboardPath'; venv\Scripts\activate; python manage.py runserver 8002"

Write-Host ""
Write-Host "All systems have been launched in separate terminals!" -ForegroundColor Green
Write-Host "FL Backend API: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "SHAP API:       http://localhost:8001/docs" -ForegroundColor Cyan
Write-Host "Dashboard:      http://localhost:8002" -ForegroundColor Cyan
Write-Host ""
Write-Host "Wait a few seconds for all the windows to initialize and start training." -ForegroundColor Yellow
Write-Host "Login to dashboard with username: admin / password: admin123" -ForegroundColor Yellow
