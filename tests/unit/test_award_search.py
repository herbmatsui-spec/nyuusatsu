import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models._generated import AwardHistory, AwardResult, Bid, Competitor, Prefecture
from services import award_search_service as service


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    yield


@pytest.fixture
def award_database(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    for model in (Bid, AwardResult, Competitor, AwardHistory, Prefecture):
        model.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(service, "get_session", sessions)
    now = dt.datetime.now()
    with sessions() as session:
        session.add_all([
            Bid(id=1, filename="test", prefecture_code="13", analyzed_at=now,
                current_status="new", created_at=now, updated_at=now),
            Prefecture(id=1, code="13", name="東京都", kana_name="とうきょうと",
                       is_active=True, priority=1, created_at=now, updated_at=now),
            Competitor(id=1, normalized_name="参加企業", is_target_company=False,
                       created_at=now, updated_at=now),
        ])
        for i in range(1, 53):
            session.add(AwardResult(
                id=i, tender_id=1 if i <= 51 else None, project_name=f"案件{i}",
                category="IT", agency_name="試験機関", winner_name="落札企業",
                winner_normalized="落札企業", award_date=dt.datetime.combine(now.date(), dt.time(23, 59)),
                created_at=now, updated_at=now, is_rebidding=False,
            ))
        session.add_all([
            AwardHistory(competitor_id=1, award_result_id=1, is_winner=False, created_at=now),
            AwardHistory(competitor_id=1, award_result_id=1, is_winner=False, created_at=now),
            AwardHistory(competitor_id=1, award_result_id=2, is_winner=True, created_at=now),
        ])
        session.commit()
    yield
    engine.dispose()


def test_region_count_and_pagination(award_database):
    params = {"prefectures": ["13"], "category": ["IT"]}
    assert service.search_award_results_count(params) == 51
    assert len(service.search_award_results(params)) == 50
    assert [r.id for r in service.search_award_results(params, offset=50)] == [1]
    assert service.search_award_results_count({"prefectures": ["27"]}) == 0
    assert service.search_award_results_count({}) == 52
    assert service.get_prefecture_options() == {"13": "東京都"}
    assert service.get_distinct_categories() == ["IT"]


def test_participants_and_date_boundary(award_database):
    today = dt.date.today()
    params = {"participant_company": "参加企業", "date_range": (today, today)}
    assert service.search_award_results_count(params) == 2
    assert [r.id for r in service.search_award_results(params)] == [2, 1]
    assert service.get_participant_names([1, 2, 3]) == {1: "参加企業", 2: "参加企業"}
    assert service.get_company_win_rate("参加企業") == {"wins": 1, "participations": 2, "win_rate": 50.0}
    assert service.search_award_results_count({"award_company": "%"}) == 0


def test_monthly_award_counts(award_database):
    this_month = dt.date.today().strftime("%Y-%m")
    assert service.get_monthly_award_counts({}) == {this_month: 52}
    assert service.get_monthly_award_counts(
        {"participant_company": "参加企業", "date_range": (dt.date.today(), dt.date.today())}
    ) == {this_month: 2}
    assert service.get_monthly_award_counts({"date_range": (dt.date(2000, 1, 1), dt.date(2000, 1, 31))}) == {}


def test_win_rate_respects_access_scope(award_database):
    service.set_access_scope({"allowed_prefectures": ["13"]})
    try:
        # AwardResult id=2 (win) is linked to Bid id=1 (Tokyo); id=1 links to tender_id=1 too.
        rate = service.get_company_win_rate("参加企業")
        assert rate == {"wins": 1, "participations": 2, "win_rate": 50.0}
    finally:
        service.set_access_scope(None)

    # With an empty allowed set (no regions granted), no records may contribute.
    service.set_access_scope({"allowed_prefectures": []})
    try:
        assert service.get_company_win_rate("参加企業") == {
            "wins": 0, "participations": 0, "win_rate": 0.0,
        }
    finally:
        service.set_access_scope(None)
