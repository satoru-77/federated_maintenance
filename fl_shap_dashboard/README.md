# FL Predictive Maintenance : Dashboard

## What this is
Django web dashboard for real-time FL monitoring.
6 pages, Tailwind CSS, Chart.js, Canvas cluster animation,
WebSocket live updates from Member 1's FL system.

## How to run
pip install -r requirements.txt
python manage.py runserver 8001

## Requires
Member 1's FastAPI running on http://localhost:8000

## Pages
/              — Overview with live accuracy chart
/simulation/   — Live cluster animation + controls
/rounds/       — Training history table
/factories/    — Factory status cards
/factories/N/  — Individual factory detail
/explainability/ — SHAP sensor importance