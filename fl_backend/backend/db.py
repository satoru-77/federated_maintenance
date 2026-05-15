# db.py
# Sets up the connection to PostgreSQL
# Everything that needs the database imports get_db from here

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from .models import Base

# Load .env file so we can read DB_HOST, DB_USER etc
load_dotenv()

# Build the connection string from environment variables
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'fl_maintenance')
DB_USER = os.getenv('DB_USER', 'fl_user')
DB_PASS = os.getenv('DB_PASSWORD', 'fl_password_123')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# create_engine makes the actual connection to PostgreSQL
engine = create_engine(DATABASE_URL, echo=False)

# SessionLocal is a factory for creating database sessions
# Each request gets its own session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """
    Creates all tables in the database if they don't exist yet.
    Safe to call multiple times — won't delete existing data.
    Call this once on startup.
    """
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")


def get_db():
    """
    Generator function that yields a database session.
    Used by FastAPI as a dependency.
    Automatically closes the session when the request is done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()