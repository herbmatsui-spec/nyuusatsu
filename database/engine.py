"""SQLAlchemy engine + session factory for the bid system.

The schema source of truth is bids_system.db (SQLite). Override via DATABASE_URL.
Both ``get_session``/``get_db`` are exposed here AND re-exported from
``database.session`` so call sites using either import path work.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB_URL = "sqlite:///./bids_system.db"
DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine: Engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Session:
    """Return a new session usable with ``with``."""
    return SessionLocal()


def get_db():
    """FastAPI/Streamlit compatible generator yielding a session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
