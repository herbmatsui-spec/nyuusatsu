from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from services.saved_search_service import SavedSearchService
from database.repositories.saved_search_repository import SavedSearchRepository
from database.repositories.notification_channel_repository import NotificationChannelRepository
from database.models.saved_search import SavedSearch
from database.models.notification_channel import NotificationChannel
from database.models.bid import Bid


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


def test_create_and_get_saved_search(db_session):
    service = SavedSearchService(db_session)
    saved = service.create(user_id="u1", name="Web制作", criteria={"keywords": "Web", "min_budget": 5000000})
    assert saved.id is not None
    loaded = service.get_active_by_user("u1")
    assert len(loaded) == 1
    assert loaded[0].name == "Web制作"


def test_match_new_bids(db_session):
    service = SavedSearchService(db_session)
    bid = Bid(filename="web.pdf", source_url="http://x/1", budget="500万円", budget_amount=5000000)
    db_session.add(bid)
    db_session.flush()
    saved = service.create(user_id="u1", name="条件", criteria={"keywords": "web"})
    matched = service.match_new_bids(saved, datetime(1970, 1, 1))
    assert len(matched) == 1
    assert matched[0]["id"] == bid.id


def test_match_new_bids_excludes_old(db_session):
    service = SavedSearchService(db_session)
    bid = Bid(filename="old.pdf", source_url="http://x/2", created_at=datetime(2020, 1, 1))
    db_session.add(bid)
    db_session.flush()
    saved = service.create(user_id="u1", name="条件", criteria={})
    matched = service.match_new_bids(saved, datetime(2021, 1, 1))
    assert matched == []


def test_channel_repository_crud(db_session):
    repo = NotificationChannelRepository(db_session)
    ch = repo.create({"user_id": "u1", "channel_type": "slack", "webhook_url": "http://h"})
    assert ch.id is not None
    loaded = repo.get_active_by_user("u1")
    assert len(loaded) == 1
    assert loaded[0].webhook_url == "http://h"
