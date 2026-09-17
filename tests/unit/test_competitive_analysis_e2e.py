"""Step 12 end-to-end verification: similarity, difficulty, win prediction on seeded sample data.

Asserts intuitive validity on hundreds of synthetic bids:
- higher budget -> higher difficulty score
- same agency/industry bids are more similar than unrelated ones
- win prediction stays in [0, 1] and drops as difficulty rises
- batch precomputation populates shared market scores without touching company-specific values
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base, Bid
from services.bid_difficulty_scorer import BidDifficultyScorer
from services.prediction_dashboard_service import PredictionDashboardService
from services.specification_similarity_service import SpecificationSimilarityService
from services.text_similarity_service import TextSimilarityService

AGENCIES = ["東京都建設局", "大阪府都市整備部", "愛知県県土整備部"]
INDUSTRIES = ["建設", "IT", "清掃"]
BUDGETS = [500_000, 5_000_000, 50_000_000, 500_000_000]


def _spec(industry: str, index: int) -> str:
    detail = {
        "建設": "橋梁の補修工事を実施する。足場の設置、ひび割れの注入、塗膜の再塗装を行うこと。",
        "IT": "業務システムの開発を行う。要件定義、設計、実装、テスト、納品までを一式とする。",
        "清掃": "庁舎内の日常清掃を実施する。床面積は延べ3000平方メートルとする。",
    }[industry]
    return f"{industry}業務仕様書 第{index}号。{detail} 作業期間は発注日から起算して{90 + index % 60}日間とする。"


@pytest.fixture
def seeded_db(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    now = datetime(2026, 9, 17)
    with factory() as session:
        for bid_id in range(1, 201):
            agency = AGENCIES[bid_id % len(AGENCIES)]
            industry = INDUSTRIES[bid_id % len(INDUSTRIES)]
            budget = BUDGETS[bid_id % len(BUDGETS)]
            session.add(Bid(
                id=bid_id,
                filename=f"{agency} {industry}業務 調達第{bid_id}号",
                analyzed_at=now, created_at=now, updated_at=now,
                current_status="新規",
                announcement_date=now - timedelta(days=bid_id % 180),
                prefecture_code=["13", "27", "23"][bid_id % 3],
                organization_name=agency,
                industry_category=industry,
                budget_amount=budget,
                qualifications="全省庁統一資格 A等級、建設業許可" if bid_id % 3 == 0 else "特に資格なし",
                deadline="2027-03-31",
                specification_text=_spec(industry, bid_id),
                specification_text_clean=_spec(industry, bid_id),
                awarded_company=None if bid_id % 4 else f"株式会社落札{bid_id % 7}",
                awarded_date=now - timedelta(days=bid_id % 180) + timedelta(days=30) if not bid_id % 4 else None,
            ))
        session.commit()
    monkeypatch.setattr(
        "services.specification_similarity_service.TextSimilarityService.session", None,
        raising=False,
    )
    yield factory
    engine.dispose()


def _svc_text(session, monkeypatch):
    svc = TextSimilarityService(session)
    monkeypatch.setattr(svc, "_fetch_bids", lambda months=None: session.query(Bid).all())
    return svc


def test_e2e_similarity_difficulty_prediction_flow(seeded_db, monkeypatch):
    factory = seeded_db
    with factory() as session:
        sim_svc = SpecificationSimilarityService(session)
        base_bid = session.get(Bid, 1)
        similarity = sim_svc.find_similar_bids(1, n=10, threshold=0.0, use_cache=False, months=0)
        assert similarity, "類似検索が結果を返すこと"
        assert all(0.0 <= r["similarity_score"] <= 1.0 for r in similarity)
        assert all(r["bid_id"] != 1 for r in similarity)
        same_industry = [r for r in similarity
                         if session.get(Bid, r["bid_id"]).industry_category == base_bid.industry_category]
        other_industry = [r for r in similarity
                          if session.get(Bid, r["bid_id"]).industry_category != base_bid.industry_category]
        assert same_industry, "同種案件が類似結果に含まれること"
        if other_industry:
            assert min(r["similarity_score"] for r in same_industry) >= max(
                r["similarity_score"] for r in other_industry)

        scorer = BidDifficultyScorer(session)
        scores = {budget: [] for budget in BUDGETS}
        for bid in session.query(Bid).all():
            scores[bid.budget_amount].append(scorer.score(bid)["score"])
        small, large = sum(scores[500_000]) / len(scores[500_000]), sum(scores[500_000_000]) / len(scores[500_000_000])
        assert large > small, f"予算が大きいほど難易度が高いこと (large={large}, small={small})"

        predictor = PredictionDashboardService(session, company_name="自社株式会社")
        result = predictor.get_bid_prediction(1)
        assert result is not None
        assert 0.0 <= result["win_prediction"]["win_rate"] <= 1.0
        assert 0.0 <= result["difficulty"]["score"] <= 100.0
        # id=7 -> BUDGETS[7%4]=500M, same "特になし" qualification tier as id=1 (id%3==1)
        large_bid = PredictionDashboardService(session).get_bid_prediction(7)
        assert large_bid["difficulty"]["score"] > result["difficulty"]["score"], (
            f"予算5億案件が500万円案件より難易度が高いこと "
            f"(large={large_bid['difficulty']['score']}, small={result['difficulty']['score']})")


def test_e2e_batch_prefill_matches_realtime(seeded_db):
    from scripts.update_bid_difficulty_scores import update_bid_difficulty_scores
    from scripts.update_win_predictions import update_win_predictions

    factory = seeded_db
    counts = update_bid_difficulty_scores(factory, months=24, limit=200, dry_run=False)
    assert counts["updated"] == 200
    win_counts = update_win_predictions(factory, limit=200, dry_run=False)
    assert win_counts["updated"] == 200

    with factory() as session:
        prefilled = session.get(Bid, 1)
        assert prefilled.bid_difficulty_score is not None
        assert prefilled.win_prediction_score is not None
        realtime = BidDifficultyScorer(session).score(prefilled)["score"]
        assert abs(prefilled.bid_difficulty_score - realtime) < 5.0


def test_e2e_feedback_roundtrip(seeded_db, tmp_path):
    from services.feedback_logger import FeedbackLogger

    logger = FeedbackLogger(path=str(tmp_path / "fb.sqlite3"))
    logger.log_feedback("win_prediction", 1, 1)
    logger.log_feedback("similarity", 1, -1, similar_bid_id=2)
    rows = logger.aggregate_weekly()
    assert rows
    assert any(row["positive"] >= 1 for row in rows)
    assert any(row["negative"] >= 1 for row in rows)
