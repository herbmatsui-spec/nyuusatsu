"""Tests for services/bid_difficulty_scorer.py"""
from __future__ import annotations

from datetime import datetime, date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.bid import Bid
from database.models import AwardResult, AwardHistory
from services.bid_difficulty_scorer import BidDifficultyScorer, DEFAULT_WEIGHTS


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


def _make_bid(session, bid_id, budget_amount=None, qualifications=None,
              deadline=None, delivery_deadline=None,
              specification_text=None, specification_text_clean=None,
              organization_name="テスト機関"):
    bid = Bid(
        id=bid_id,
        filename=f"bid_{bid_id}.pdf",
        current_status="入札済",
        analyzed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        budget_amount=budget_amount,
        qualifications=qualifications,
        deadline=deadline,
        delivery_deadline=delivery_deadline,
        specification_text=specification_text,
        specification_text_clean=specification_text_clean,
        organization_name=organization_name,
    )
    session.add(bid)
    session.flush()
    return bid


def test_score_budget_high(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1, budget_amount=10_000_000)  # 10M
    result = svc.score(bid)
    assert result["score"] > 0
    assert 0.0 <= result["breakdown"]["budget"] <= 1.0


def test_score_budget_low(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1, budget_amount=1000)  # 1K
    result = svc.score(bid)
    assert result["breakdown"]["budget"] < 0.5


def test_score_budget_zero(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1, budget_amount=0)
    assert svc._score_budget(bid) == 0.0


def test_score_budget_none(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1)
    assert svc._score_budget(bid) == 0.0


def test_score_qualifications(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(
        db_session, 1,
        qualifications="・要件1\n・要件2\n・要件3",
    )
    score = svc._score_qualifications(bid)
    assert 0.0 < score <= 1.0
    # 3 items out of 15 max
    assert abs(score - 3 / 15.0) < 0.001


def test_score_qualifications_none(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1)
    assert svc._score_qualifications(bid) == 0.0


def test_score_qualifications_many(db_session):
    svc = BidDifficultyScorer(db_session)
    items = "\n".join(f"・要件{i}" for i in range(20))
    bid = _make_bid(db_session, 1, qualifications=items)
    score = svc._score_qualifications(bid)
    assert score == 1.0  # capped at 1.0


def test_score_deadline_short(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1, delivery_deadline=date.today() + timedelta(days=5))
    score = svc._score_deadline(bid)
    assert 0.0 < score <= 1.0
    # 5 days -> high score (close to 1.0)
    assert score > 0.5


def test_score_deadline_long(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1, delivery_deadline=date.today() + timedelta(days=120))
    score = svc._score_deadline(bid)
    # 120 days -> low score (0.0)
    assert score == 0.0


def test_score_deadline_past(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1, delivery_deadline=date.today() - timedelta(days=1))
    assert svc._score_deadline(bid) == 1.0


def test_score_deadline_none(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1)
    score = svc._score_deadline(bid)
    assert 0.0 <= score <= 1.0


def test_score_deadline_from_string(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(
        db_session, 1,
        delivery_deadline=None,
        deadline="2026-12-31",
    )
    score = svc._score_deadline(bid)
    assert 0.0 <= score <= 1.0


def test_score_competition_rate_with_data(db_session):
    svc = BidDifficultyScorer(db_session)
    # Create an AwardResult with agency name matching the bid
    ar = AwardResult(
        tender_id=1,
        agency_name="テスト機関",
        announcement_date=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        winner_count=2,
        is_rebidding=False,
    )
    db_session.add(ar)
    db_session.flush()

    # Create AwardHistory entries (3 competitors)
    for i in range(3):
        ah = AwardHistory(
            competitor_id=i + 1,
            award_result_id=ar.id,
            is_winner=(i == 0),
            created_at=datetime.utcnow(),
        )
        db_session.add(ah)
    db_session.flush()

    bid = _make_bid(db_session, 1)
    score = svc._score_competition_rate(bid)
    assert 0.0 < score <= 1.0
    # 3 bidders / 15 max
    assert abs(score - 3 / 15.0) < 0.001


def test_score_competition_rate_no_data(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1)
    score = svc._score_competition_rate(bid)
    # Should return default competition score
    assert 0.0 <= score <= 1.0


def test_score_spec_length(db_session):
    svc = BidDifficultyScorer(db_session)
    short_text = "短い"
    long_text = "あ" * 10000
    bid_short = _make_bid(db_session, 1, specification_text=short_text)
    bid_long = _make_bid(db_session, 2, specification_text=long_text)

    assert svc._score_spec_length(bid_short) <= svc._score_spec_length(bid_long)
    assert svc._score_spec_length(bid_long) > 0


def test_score_spec_length_none(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1)
    assert svc._score_spec_length(bid) == 0.0


def test_score_overall(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(
        db_session, 1,
        budget_amount=5_000_000,
        qualifications="・項目1\n・項目2\n・項目3\n・項目4",
        specification_text="A" * 500,
        specification_text_clean="A" * 500,
        delivery_deadline=date.today() + timedelta(days=14),
    )
    result = svc.score(bid)
    assert "score" in result
    assert "breakdown" in result
    assert "weights" in result
    assert 0.0 <= result["score"] <= 100.0
    assert len(result["breakdown"]) == 5
    assert len(result["weights"]) == 5


def test_score_higher_budget_higher_difficulty(db_session):
    svc = BidDifficultyScorer(db_session)
    low_budget = _make_bid(db_session, 1, budget_amount=100_000)
    high_budget = _make_bid(db_session, 2, budget_amount=100_000_000)
    low_score = svc.score(low_budget)
    high_score = svc.score(high_budget)
    assert high_score["score"] > low_score["score"]
    assert high_score["breakdown"]["budget"] > low_score["breakdown"]["budget"]


def test_score_shorter_deadline_higher_difficulty(db_session):
    svc = BidDifficultyScorer(db_session)
    long_deadline = _make_bid(db_session, 1, delivery_deadline=date.today() + timedelta(days=90))
    short_deadline = _make_bid(db_session, 2, delivery_deadline=date.today() + timedelta(days=7))
    assert svc.score(short_deadline)["breakdown"]["deadline"] > svc.score(long_deadline)["breakdown"]["deadline"]


def test_get_score_breakdown_text(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(
        db_session, 1,
        budget_amount=1_000_000,
        qualifications="・項目1\n・項目2",
        specification_text="テスト仕様書" * 10,
        delivery_deadline=date.today() + timedelta(days=14),
    )
    result = svc.score(bid)
    text = svc.get_score_breakdown_text(result)
    assert "難易度スコアの計算内訳" in text
    assert "budget" in text
    assert "合計" in text


def test_missing_evidence_is_not_easy_bid(db_session):
    bid = _make_bid(db_session, 1)
    result = BidDifficultyScorer(db_session).score(bid)
    assert result["confidence"]["evidence_coverage"] == 0
    assert set(result["confidence"]["missing_factors"]) == set(DEFAULT_WEIGHTS)
    assert result["confidence"]["calibrated"] is False
    assert result["breakdown"]["budget"] == 0.5
    assert result["breakdown"]["spec_length"] == 0.5
    assert result["breakdown"]["deadline"] < 1


def test_competition_average_has_context_and_time_boundaries(db_session):
    bid = _make_bid(db_session, 1)
    bid.industry_category = "IT"
    bid.announcement_date = datetime(2025, 6, 1)
    cases = [
        (2, "IT", -1, None),
        (6, "IT", -365, None),
        (15, "IT", -366, None),
        (15, "建設", -10, None),
        (15, "IT", 0, None),
        (15, "IT", 10, None),
        (15, "IT", -10, bid.id),
        (15, "IT", None, None),
    ]
    for count, category, days, tender_id in cases:
        ar = AwardResult(
            agency_name=bid.organization_name, category=category,
            award_date=bid.announcement_date + timedelta(days=days) if days is not None else None,
            tender_id=tender_id, is_rebidding=False,
            created_at=datetime.now(), updated_at=datetime.now(),
        )
        db_session.add(ar)
        db_session.flush()
        for competitor_id in list(range(1, count + 1)) + [1]:
            db_session.add(AwardHistory(
                award_result_id=ar.id, competitor_id=competitor_id,
                is_winner=competitor_id == 1, created_at=datetime.now(),
            ))
    db_session.flush()
    result = BidDifficultyScorer(db_session).score(bid)
    assert result["breakdown"]["competition_rate"] == pytest.approx(4 / 15, abs=0.0001)
    assert result["confidence"]["sample_counts"]["competition_rate"] == 2


def test_spec_length_uses_preprocessed_text_and_respects_clean_empty(db_session):
    svc = BidDifficultyScorer(db_session)
    bid = _make_bid(db_session, 1, specification_text="<p>実績3年以上</p><script>noise</script>")
    assert svc._get_spec_text(bid) == "実績3年以上"
    bid.specification_text_clean = ""
    assert svc._get_spec_text(bid) == ""
    assert "spec_length" in svc.score(bid)["confidence"]["missing_factors"]


def test_deadline_falls_back_after_invalid_delivery_date(db_session):
    bid = Bid(delivery_deadline="不明", deadline="2026-12-31")
    assert BidDifficultyScorer(db_session)._extract_deadline_date(bid) == date(2026, 12, 31)


def test_default_weights():
    assert DEFAULT_WEIGHTS["budget"] == 0.30
    assert DEFAULT_WEIGHTS["qualifications"] == 0.20
    assert DEFAULT_WEIGHTS["deadline"] == 0.20
    assert DEFAULT_WEIGHTS["competition_rate"] == 0.15
    assert DEFAULT_WEIGHTS["spec_length"] == 0.15


def test_weights_sum_to_one():
    total = sum(DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001
