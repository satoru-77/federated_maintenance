# seed.py
# Adds the 4 factories to the database
# Run once: python -m backend.seed
# Safe to run again — won't duplicate if already exists

from .db import SessionLocal, create_tables
from .models import Factory

FACTORIES = [
    {"factory_id": 1, "name": "Factory Mumbai",  "dataset": "FD001", "n_engines": 100},
    {"factory_id": 2, "name": "Factory Berlin",  "dataset": "FD002", "n_engines": 260},
    {"factory_id": 3, "name": "Factory Detroit", "dataset": "FD003", "n_engines": 100},
    {"factory_id": 4, "name": "Factory Tokyo",   "dataset": "FD004", "n_engines": 248},
]

def seed():
    create_tables()
    db = SessionLocal()

    for data in FACTORIES:
        existing = db.query(Factory).filter(
            Factory.factory_id == data['factory_id']
        ).first()

        if not existing:
            factory = Factory(**data)
            db.add(factory)
            print(f"Added: {data['name']}")
        else:
            print(f"Already exists: {data['name']}")

    db.commit()
    db.close()
    print("Seeding complete.")

if __name__ == '__main__':
    seed()