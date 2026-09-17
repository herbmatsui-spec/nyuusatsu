"""Tests for services/win_prediction_service.py"""
from __future__ import annotations

from datetime import datetime, date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.bid import Bid
from database.models import Competitor, CompanyProfile, AwardResult, AwardHistory
from services.win_prediction_service import WinPredictionService, DEFAULT_WEIGHTS, DEFAULT_PARAMS


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


def _make_bid(session, bid_id, organization_name="テスト機関", qualifications=None,
              budget_amount=5000000, delivery_deadline=None):
    bid = Bid(
        id=bid_id,
        filename=f"bid_{bid_id}.pdf",
        current_status="入札済",
        analyzed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        organization_name=organization_name,
        qualifications=qualifications,
        budget_amount=budget_amount,
        prefecture_code="13",
        industry_category="IT",
        announcement_date=datetime.utcnow() - timedelta(days=30),
        delivery_deadline=delivery_deadline or (date.today() + timedelta(days=14)),
    )
    session.add(bid)
    session.flush()
    return bid


def _make_competitor(session, name="サンプル株式会社"):
    c = Competitor(
        normalized_name=name,
        raw_names=name,
        industry_category="IT",
        region="東京都",
        is_target_company=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(c)
    session.flush()
    return c


def _make_company_profile(session, name="サンプル株式会社", grade="A"):
    cp = CompanyProfile(
        name=name,
        unified_qualification_grade=grade,
        unified_qualification_expire=datetime.now() + timedelta(days=365),
        industry_category="IT",
        region="東京都",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(cp)
    session.flush()
    return cp


def _make_award_history(session, competitor_id, agency_name, is_winner=True):
    ar = AwardResult(
        tender_id=None,
        agency_name=agency_name,
        category="IT",
        budget_amount=5000000,
        announcement_date=datetime.utcnow() - timedelta(days=10),
        award_date=datetime.utcnow() - timedelta(days=5),
        winner_count=2,
        is_rebidding=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(ar)
    session.flush()

    ah = AwardHistory(
        competitor_id=competitor_id,
        award_result_id=ar.id,
        is_winner=is_winner,
        created_at=datetime.utcnow(),
    )
    session.add(ah)
    session.flush()
    return ar, ah


def test_predict_with_company_name(db_session):
    competitor = _make_competitor(db_session)
    _make_company_profile(db_session, grade="A")
    _make_bid(db_session, 1)

    svc = WinPredictionService(db_session, company_name="サンプル株式会社")
    bid = db_session.get(Bid, 1)
    result = svc.predict(bid)

    assert "win_rate" in result
    assert "breakdown" in result
    assert "difficulty_score" in result
    assert "weights" in result
    assert 0.0 <= result["win_rate"] <= 1.0
    assert len(result["breakdown"]) == 4


def test_predict_difficulty_inverse(db_session):
    _make_bid(db_session, 1, budget_amount=100_000)  # Low budget = low difficulty
    svc = WinPredictionService(db_session, company_name="テスト")
    bid = db_session.get(Bid, 1)
    difficulty = svc.difficulty_scorer.score(bid)["score"]
    result = svc.predict(bid)
    expected_inverse = 1.0 - (difficulty / 100.0 * 0.5)
    assert abs(result["breakdown"]["difficulty_inverse"] - round(expected_inverse, 4)) < 0.01


def test_company_win_rate_with_history(db_session):
    competitor = _make_competitor(db_session)
    # Create 4 award history entries: 2 wins, 2 losses
    for i in range(2):
        _make_award_history(db_session, competitor.id, "テスト機関", is_winner=True)
    for i in range(2):
        _make_award_history(db_session, competitor.id, "テスト機関", is_winner=False)

    _make_bid(db_session, 1)
    svc = WinPredictionService(db_session, company_name="サンプル株式会社")
    bid = db_session.get(Bid, 1)
    result = svc.predict(bid)

    assert svc._get_company_win_rate() == 0.5
    assert result["breakdown"]["company_win_rate"] == DEFAULT_PARAMS["default_company_win_rate"]
    assert result["breakdown"]["agency_award_trend"] == DEFAULT_PARAMS["default_agency_award_rate"]
    assert result["confidence"]["sample_counts"]["company_win_rate"] == 0


def test_company_win_rate_no_history(db_session):
    _make_bid(db_session, 1)
    svc = WinPredictionService(db_session, company_name="存在しない会社")
    bid = db_session.get(Bid, 1)
    result = svc.predict(bid)
    # No history -> default
    assert result["breakdown"]["company_win_rate"] == DEFAULT_PARAMS["default_company_win_rate"]


def test_qualification_match_full(db_session):
    _make_company_profile(db_session, grade="A")
    bid = _make_bid(
        db_session, 1,
        qualifications="全省庁統一資格 A等級が必要です。",
    )
    svc = WinPredictionService(db_session, company_name="サンプル株式会社")
    result = svc.predict(bid)
    assert result["breakdown"]["qualification_match"] == 1.0


def test_qualification_match_partial(db_session):
    _make_company_profile(db_session, grade="B")
    bid = _make_bid(
        db_session, 1,
        qualifications="全省庁統一資格 A等級が必要です。",
    )
    svc = WinPredictionService(db_session, company_name="サンプル株式会社")
    result = svc.predict(bid)
    # Company B cannot apply to A requirement
    assert result["breakdown"]["qualification_match"] == 0.0


def test_qualification_match_does_not_assume_higher_grade_eligible(db_session):
    _make_company_profile(db_session, grade="A")
    bid = _make_bid(
        db_session, 1,
        qualifications="全省庁統一資格 B等級が必要です。",
    )
    svc = WinPredictionService(db_session, company_name="サンプル株式会社")
    result = svc.predict(bid)
    assert result["breakdown"]["qualification_match"] == 0.0


def test_qualification_match_no_grade_requirement(db_session):
    _make_company_profile(db_session, grade="A")
    bid = _make_bid(
        db_session, 1,
        qualifications="資格要件は特になし",
    )
    svc = WinPredictionService(db_session, company_name="サンプル株式会社")
    result = svc.predict(bid)
    assert result["breakdown"]["qualification_match"] == 1.0


def test_qualification_match_no_company_grade(db_session):
    bid = _make_bid(
        db_session, 1,
        qualifications="全省庁統一資格 A等級",
    )
    svc = WinPredictionService(db_session, company_name="サンプル株式会社")
    result = svc.predict(bid)
    # No profile -> default
    assert result["breakdown"]["qualification_match"] == DEFAULT_PARAMS["default_qualification_match"]


def test_predict_with_competitor_id(db_session):
    competitor = _make_competitor(db_session)
    _make_company_profile(db_session, grade="A")
    _make_bid(db_session, 1)
    svc = WinPredictionService(db_session, competitor_id=competitor.id)
    bid = db_session.get(Bid, 1)
    result = svc.predict(bid)
    assert 0.0 <= result["win_rate"] <= 1.0


def test_predict_high_difficulty_lower_win_rate(db_session):
    # High budget, tight deadline, many qualifications -> high difficulty
    bid_high = _make_bid(
        db_session, 1,
        budget_amount=100_000_000,  # Very high
        qualifications="・要件1\n・要件2\n・要件3\n・要件4\n・要件5\n・要件6\n・要件7\n・要件8\n・要件9\n・要件10",
        delivery_deadline=date.today() + timedelta(days=3),  # Tight
    )
    # Low difficulty: low budget, long deadline
    bid_low = _make_bid(
        db_session, 2,
        budget_amount=100_000,  # Low
        qualifications="・項目1",
        delivery_deadline=date.today() + timedelta(days=120),  # Long
    )

    svc = WinPredictionService(db_session, company_name="テスト")
    high_result = svc.predict(bid_high)
    low_result = svc.predict(bid_low)

    assert high_result["breakdown"]["difficulty_inverse"] < low_result["breakdown"]["difficulty_inverse"]
    assert high_result["difficulty_score"] > low_result["difficulty_score"]


def test_get_win_rate_breakdown_text(db_session):
    _make_company_profile(db_session, grade="A")
    _make_bid(db_session, 1)
    svc = WinPredictionService(db_session, company_name="サンプル株式会社")
    bid = db_session.get(Bid, 1)
    result = svc.predict(bid)
    text = svc.get_win_rate_breakdown_text(result)
    assert "勝率予測の計算内訳" in text
    assert "company_win_rate" in text
    assert "合計勝率" in text


@pytest.mark.parametrize("text", [None, "", "API対応", "CAD実績", "ISO9001認証", "甲社との契約", "全省庁統一資格 B等級以上", "全省庁統一資格 A等級、ISO9001必須"])
def test_unknown_qualification_is_not_positive_evidence(db_session, text):
    _make_company_profile(db_session)
    bid = _make_bid(db_session, 1, qualifications=text)
    result = WinPredictionService(db_session, company_name="サンプル株式会社").predict(bid)
    assert result["breakdown"]["qualification_match"] == 0.5
    assert "qualification_match" in result["confidence"]["missing_factors"]


@pytest.mark.parametrize("text", ["全省庁統一資格 Ａ等級", "全省庁統一資格 B又はA等級", "全省庁統一資格「A」又は「B」のいずれか"])
def test_explicit_grade_alternatives(db_session, text):
    _make_company_profile(db_session)
    bid = _make_bid(db_session, 1, qualifications=text)
    assert WinPredictionService(db_session, company_name="サンプル株式会社")._get_qualification_match(bid) == 1


@pytest.mark.parametrize("days,expected,status", [(None, 0.5, "unknown_expiry"), (-1, 0, "expired"), (0, 1, "matched")])
def test_qualification_expiry(db_session, days, expected, status):
    profile = _make_company_profile(db_session)
    profile.unified_qualification_expire = datetime.now() + timedelta(days=days) if days is not None else None
    bid = _make_bid(db_session, 1, qualifications="全省庁統一資格 A等級")
    result = WinPredictionService(db_session, company_name="サンプル株式会社").predict(bid)
    assert result["breakdown"]["qualification_match"] == expected
    assert result["confidence"]["qualification_status"] == status


def test_both_stored_and_input_company_names_are_normalized(db_session):
    competitor = _make_competitor(db_session, name="（株） サンプル")
    profile = _make_company_profile(db_session, name="㈱サンプル")
    svc = WinPredictionService(db_session, company_name="株式会社 サンプル")
    assert svc._resolve_competitor().id == competitor.id
    assert svc._get_company_profile().id == profile.id
    assert WinPredictionService(db_session, competitor_id=competitor.id)._get_company_profile().id == profile.id


def test_contextual_history_and_agency_share_exclude_leakage(db_session):
    competitor = _make_competitor(db_session)
    target = _make_bid(db_session, 1)
    target.announcement_date = datetime(2025, 6, 1)
    cases = [
        ("IT", "13", 5_000_000, -1, True),
        ("IT", "13", 1_000_000, -365, False),
        ("建設", "13", 5_000_000, -1, True),
        ("IT", "27", 5_000_000, -1, True),
        ("IT", "13", 10_000_000, -1, True),
        ("IT", "13", 5_000_000, 0, True),
        ("IT", "13", 5_000_000, 1, True),
        ("IT", "13", 5_000_000, None, True),
    ]
    for index, (industry, region, budget, days, won) in enumerate(cases, 2):
        historical = _make_bid(db_session, index, budget_amount=budget)
        historical.industry_category = industry
        historical.prefecture_code = region
        ar, ah = _make_award_history(db_session, competitor.id, "テスト機関", won)
        ar.tender_id = historical.id
        ar.category = industry
        ar.budget_amount = budget
        ar.award_date = target.announcement_date + timedelta(days=days) if days is not None else None
        ar.winner_name = "サンプル株式会社" if won else "別会社"
    target_award, _ = _make_award_history(db_session, competitor.id, "テスト機関", True)
    target_award.tender_id = target.id
    target_award.award_date = target.announcement_date - timedelta(days=1)
    stale, _ = _make_award_history(db_session, competitor.id, "テスト機関", True)
    stale.award_date = target.announcement_date - timedelta(days=366)
    other = AwardResult(
        agency_name="テスト機関", award_date=target.announcement_date - timedelta(days=5),
        winner_name="別会社", is_rebidding=False, created_at=datetime.now(), updated_at=datetime.now(),
    )
    db_session.add(other)
    db_session.flush()
    svc = WinPredictionService(db_session, competitor_id=competitor.id)
    result = svc.predict(target)
    assert result["breakdown"]["company_win_rate"] == 0.5
    assert result["confidence"]["sample_counts"]["company_win_rate"] == 2
    assert result["breakdown"]["agency_award_trend"] == pytest.approx(4 / 6, abs=0.0001)
    assert result["confidence"]["sample_counts"]["agency_award_trend"] == 6
    assert svc._get_company_win_rate(target) == 0.5
    assert result["score_kind"] == "uncalibrated_rule_based_score"
    assert result["confidence"]["calibrated"] is False


def test_missing_context_and_no_data_have_zero_coverage(db_session):
    bid = Bid()
    result = WinPredictionService(db_session).predict(bid)
    assert result["confidence"]["evidence_coverage"] == 0
    assert set(result["confidence"]["missing_context"]) == {"industry", "region", "budget_band"}
    assert set(result["confidence"]["missing_factors"]) == set(DEFAULT_WEIGHTS)
    assert set(result["confidence"]["sample_counts"].values()) == {0}


def test_default_weights():
    assert DEFAULT_WEIGHTS["company_win_rate"] == 0.40
    assert DEFAULT_WEIGHTS["difficulty_inverse"] == 0.30
    assert DEFAULT_WEIGHTS["agency_award_trend"] == 0.20
    assert DEFAULT_WEIGHTS["qualification_match"] == 0.10


def test_default_params():
    assert DEFAULT_PARAMS["default_company_win_rate"] == 0.15
    assert DEFAULT_PARAMS["default_agency_award_rate"] == 0.30
    assert DEFAULT_PARAMS["default_qualification_match"] == 0.50


def test_weights_sum_to_one():
    total = sum(DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001


def test_win_rate_clipped(db_session):
    # With no company info, all defaults should produce a valid 0-1 rate
    _make_bid(db_session, 1)
    svc = WinPredictionService(db_session, company_name="存在しない")
    bid = db_session.get(Bid, 1)
    result = svc.predict(bid)
    assert 0.0 <= result["win_rate"] <= 1.0
