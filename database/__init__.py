"""Database package.

Re-exports the shared declarative ``Base``, the engine, and session helpers so
that both ``from database import Base`` and ``from database.base import Base``
resolve to the same object.
"""
from .base import Base, engine, SessionLocal, get_session, get_db  # noqa: F401
