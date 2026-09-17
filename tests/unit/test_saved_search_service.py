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
    from database.models import User
    from datetime import datetime
    import json
    # Create a user
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        password_hash="hash",
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    
    service = SavedSearchService(db_session)
    criteria = {"keywords": "Web", "min_budget": 5000000}
    saved = service.create(user_id="1", name="Web制作", criteria_json=json.dumps(criteria))
    assert saved.id is not None
    loaded = service.get_active_by_user("1")
    assert len(loaded) == 1
    assert loaded[0].name == "Web制作"


def test_match_new_bids(db_session):
    from database.models import User, Bid
    from datetime import datetime
    import json
    # Create a user
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        password_hash="hash",
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    # Create a bid
    bid = Bid(
        filename="web.pdf",
        source_url="http://x/1",
        budget="500万円",
        budget_amount=5000000,
        analyzed_at=datetime.utcnow(),
        current_status="未確認",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(bid)
    db_session.flush()
    service = SavedSearchService(db_session)
    criteria = {"keywords": "web"}
    saved = service.create(user_id="1", name="条件", criteria_json=json.dumps(criteria))
    matched = service.match_new_bids(saved, datetime(1970, 1, 1))
    assert len(matched) == 1
    assert matched[0]["id"] == bid.id


def test_match_new_bids_excludes_old(db_session):
    import json
    from database.models import User, Bid
    from datetime import datetime
    # Create a user
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        password_hash="hash",
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    # Create a bid
    bid = Bid(
        filename="old.pdf",
        source_url="http://x/2",
        created_at=datetime(2020, 1, 1),
        analyzed_at=datetime.utcnow(),
        current_status="未確認",
        updated_at=datetime.utcnow(),
    )
    db_session.add(bid)
    db_session.flush()
    service = SavedSearchService(db_session)
    saved = service.create(user_id="1", name="条件", criteria_json=json.dumps({}))
    matched = service.match_new_bids(saved, datetime(2021, 1, 1))
    assert matched == []


def test_channel_repository_crud(db_session):
    repo = NotificationChannelRepository(db_session)
    now = datetime.utcnow()
    ch = repo.create(
        user_id="u1",
        channel_type="slack",
        webhook_url="http://h",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    assert ch.id is not None
    loaded = repo.get_active_by_user("u1")
    assert len(loaded) == 1
    assert loaded[0].webhook_url == "http://h"
