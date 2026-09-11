from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from services.kanban_service import KanbanService
from database.models.bid import Bid
from database.models.bid_assignment import BidAssignment


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


def test_move_card(db_session):
    bid = Bid(
        filename="a.pdf",
        source_url="http://x/1",
        current_status="未確認",
        analyzed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(bid)
    db_session.flush()
    service = KanbanService(db_session)
    updated = service.move_card(bid.id, "検討中", "u1")
    assert updated.current_status == "検討中"


def test_get_board_groups_by_status(db_session):
    bid1 = Bid(
        filename="a.pdf",
        source_url="http://x/1",
        current_status="未確認",
        analyzed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    bid2 = Bid(
        filename="b.pdf",
        source_url="http://x/2",
        current_status="検討中",
        analyzed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add_all([bid1, bid2])
    db_session.flush()
    service = KanbanService(db_session)
    board = service.get_board()
    assert len(board["未確認"]) == 1
    assert len(board["検討中"]) == 1


def test_assign_and_unassign(db_session):
    bid = Bid(
        filename="a.pdf",
        source_url="http://x/1",
        current_status="未確認",
        analyzed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(bid)
    db_session.flush()
    service = KanbanService(db_session)
    service.assign_user(bid.id, "u1", "owner")
    assignments = service.assignment_repo.get_by_bid(bid.id)
    assert len(assignments) == 1
    service.unassign_user(bid.id, "u1")
    assignments = service.assignment_repo.get_by_bid(bid.id)
    assert assignments == []
