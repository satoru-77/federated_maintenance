# start_fl.ps1
# Starts all FL components in separate terminals
# Run from fl_backend/ folder:
#   .\start_fl.ps1

Write-Host "Starting FL Predictive Maintenance System..." -ForegroundColor Green

# Terminal 1 — FastAPI backend
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; uvicorn backend.main:app --reload --port 8000"

Start-Sleep -Seconds 5

# Terminal 2 — Flower server
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; python -m server.server --rounds 20 --algorithm FedAvg"

Start-Sleep -Seconds 10

# Terminal 3 — Factory 1 (FD001 — Mumbai)
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; python -m client.client --factory-id 1"

Start-Sleep -Seconds 1

# Terminal 4 — Factory 2 (FD002 — Berlin)
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; python -m client.client --factory-id 2"

Start-Sleep -Seconds 1

# Terminal 5 — Factory 3 (FD003 — Detroit)
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; python -m client.client --factory-id 3"

Start-Sleep -Seconds 1

# Terminal 6 — Factory 4 (FD004 — Tokyo)
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$PWD'; venv\Scripts\activate; python -m client.client --factory-id 4"

Write-Host ""
Write-Host "All components started!" -ForegroundColor Green
Write-Host "FastAPI docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Rounds data:  http://localhost:8000/rounds" -ForegroundColor Cyan