from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from services.price_prediction_service import PricePredictionService
from services.win_rate_service import WinRateService
from database.models.bid import Bid
from database.models.award_result import AwardResult


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


def test_win_rate_summary_empty(db_session):
    service = WinRateService()
    result = service.summarize([])
    assert result["count"] == 0


def test_win_rate_summary_with_data(db_session):
    service = WinRateService()
    data = [
        {"award_rate": 0.8, "contract_amount": 100},
        {"award_rate": 0.9, "contract_amount": 200},
    ]
    result = service.summarize(data)
    assert result["count"] == 2
    assert result["median_award_rate"] == 0.85


def test_price_prediction_not_found(db_session):
    service = PricePredictionService(db_session)
    result = service.predict(9999, [], 1000000)
    assert "error" in result
