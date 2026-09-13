from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from services.milestone_service import MilestoneService
from services.ical_exporter import generate_ics
from database.models.extraction_result import ExtractionResult
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


def _create_bid(session, name="テスト案件") -> Bid:
    bid = Bid(
        filename=f"{name}.pdf",
        source_url="http://example.com/x.pdf",
        analyzed_at=datetime.utcnow(),
        current_status="未確認",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(bid)
    session.flush()
    return bid


def test_get_upcoming_empty(db_session):
    service = MilestoneService(db_session)
    result = service.get_upcoming(days=30)
    assert result == []


def test_get_upcoming_filters_correctly(db_session):
    bid = _create_bid(db_session)
    ext = ExtractionResult(
        filename=bid.filename,
        bid_id=bid.id,
        question_deadline=date.today(),
        submit_deadline=date.today() + __import__("datetime").timedelta(days=10),
        opening_date=date.today() + __import__("datetime").timedelta(days=5),
        raw_text_length=100,
        created_at=datetime.utcnow(),
    )
    db_session.add(ext)
    db_session.flush()

    service = MilestoneService(db_session)
    result = service.get_upcoming(days=30)
    assert len(result) == 3
    types = {r["type"] for r in result}
    assert types == {"質問回答期限", "申請書提出期限", "開札日"}


def test_get_by_bid(db_session):
    bid1 = _create_bid(db_session, name="案件A")
    bid2 = _create_bid(db_session, name="案件B")
    ext1 = ExtractionResult(
        filename=bid1.filename,
        bid_id=bid1.id,
        submit_deadline=date.today(),
        raw_text_length=100,
        created_at=datetime.utcnow(),
    )
    ext2 = ExtractionResult(
        filename=bid2.filename,
        bid_id=bid2.id,
        submit_deadline=date.today(),
        raw_text_length=100,
        created_at=datetime.utcnow(),
    )
    db_session.add_all([ext1, ext2])
    db_session.flush()

    service = MilestoneService(db_session)
    result = service.get_by_bid(bid1.id)
    assert len(result) == 1
    assert result[0]["bid_id"] == bid1.id


def test_generate_ics():
    milestones = [
        {"bid_id": 1, "filename": "a.pdf", "type": "開札日", "date": date(2026, 8, 1)},
    ]
    data = generate_ics(milestones)
    assert b"BEGIN:VCALENDAR" in data
    assert b"END:VCALENDAR" in data
    assert b"20260801" in data
    assert "開札日".encode("utf-8") in data
