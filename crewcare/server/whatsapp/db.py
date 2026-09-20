"""
Placeholder DB wiring so this package is runnable/testable standalone.
In the real app, delete this and import your existing SessionLocal/engine
and Base.metadata from wherever the rest of the schema lives, then run
Base.metadata.create_all(engine) once at startup (or use Alembic migrations).
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./stationshield_whatsapp.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
