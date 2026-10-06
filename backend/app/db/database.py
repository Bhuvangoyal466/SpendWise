"""
Database engine and session management.

Uses SQLite by default (zero-setup, good for dev/demo/grading) but is written
against plain SQLAlchemy so swapping to Postgres in production is a one-line
change of DATABASE_URL, e.g.:

    DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/spendwise
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./spendwise.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
