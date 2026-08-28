"""Shared declarative base and convenience re-exports.

Tests and app code import ``Base`` from here so that all generated models
(defined in ``database.models._generated``) are registered on the same
metadata instance.
"""
from .models._generated import Base  # noqa: F401  (single shared Base)
from .engine import engine, SessionLocal, get_session, get_db  # noqa: F401
