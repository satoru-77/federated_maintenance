# FL Predictive Maintenance : Backend

## What this is :
Federated Learning infrastructure for industrial predictive maintenance.
Flower server, 4 factory clients, FastAPI, PostgreSQL, adaptive clustering,
differential privacy, Byzantine fault detection.

## How to run
docker-compose up --build

## API
http://localhost:8000/docs

## FL Training
python -m server.server --rounds 20 --algorithm FedAvg
python -m client.client --factory-id 1
python -m client.client --factory-id 2
python -m client.client --factory-id 3
python -m client.client --factory-id 4