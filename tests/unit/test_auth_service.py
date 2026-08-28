from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from services.auth_service import AuthService
from database.models.user import User
from database.models.role import Role, UserRole
from database.models.organization import Organization


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_authenticate_success(db_session):
    auth = AuthService(db_session)
    auth.create_user("alice", "password")
    user = auth.authenticate("alice", "password")
    assert user is not None
    assert user.username == "alice"


def test_authenticate_failure(db_session):
    auth = AuthService(db_session)
    auth.create_user("alice", "password")
    user = auth.authenticate("alice", "wrong")
    assert user is None


def test_has_permission(db_session):
    auth = AuthService(db_session)
    user = auth.create_user("alice", "password")
    role = Role(name="admin", permissions_json='["bid:read", "bid:write"]')
    db_session.add(role)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.flush()
    assert auth.has_permission(user, "read", "bid") is True
    assert auth.has_permission(user, "write", "bid") is True
    assert auth.has_permission(user, "delete", "bid") is False
