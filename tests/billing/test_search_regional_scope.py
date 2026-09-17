"""Minimal tests for search-scope behavior (regional pricing, search paths)."""
import json
from types import SimpleNamespace
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Bid
from services import search_service
from utils.plan_gate import get_search_prefecture_scope


def make_user(plan, prefectures=None, trial_ends_at=None):
    return SimpleNamespace(
        id=1, plan=plan, trial_ends_at=trial_ends_at,
        allowed_prefectures=json.dumps(prefectures) if prefectures is not None else None,
    )


class TestScopeResolution:
    def test_no_user_is_unrestricted(self):
        assert get_search_prefecture_scope(None) is None

    def test_national_plan_is_unrestricted(self):
        assert get_search_prefecture_scope(make_user("national", ["13"])) is None

    def test_pro_plan_is_unrestricted(self):
        assert get_search_prefecture_scope(make_user("pro", ["13"])) is None

    def test_active_trial_is_unrestricted(self):
        user = make_user("free", ["13"], trial_ends_at=datetime(2099, 1, 1))
        assert get_search_prefecture_scope(user) is None

    def test_expired_trial_free_user_with_no_selection_is_empty(self):
        user = make_user("free", None, trial_ends_at=datetime(2020, 1, 1))
        assert get_search_prefecture_scope(user) == []

    def test_single_region_returns_selection(self):
        assert get_search_prefecture_scope(make_user("single_region", ["13"])) == ["13"]

    def test_dual_region_returns_both(self):
        assert get_search_prefecture_scope(make_user("dual_region", ["13", "27"])) == ["13", "27"]

    def test_restricted_with_no_selection_is_empty_not_unlimited(self):
        assert get_search_prefecture_scope(make_user("dual_region", None)) == []

    def test_invalid_codes_are_filtered(self):
        assert get_search_prefecture_scope(make_user("dual_region", ["13", "99", "abc"])) == ["13"]

    def test_non_list_json_is_empty(self):
        user = SimpleNamespace(id=1, plan="single_region", trial_ends_at=None,
                               allowed_prefectures='{"13": true}')
        assert get_search_prefecture_scope(user) == []


@pytest.fixture
def scope_db(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Bid.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    now = datetime(2026, 9, 17)
    with factory() as session:
        for bid_id, pref in [(1, "13"), (2, "27"), (3, "13"), (4, None)]:
            session.add(Bid(
                id=bid_id, filename=f"案件{bid_id}", prefecture_code=pref,
                organization_name="東京都", analyzed_at=now, created_at=now,
                updated_at=now, current_status="新規", announcement_date=now,
            ))
        session.commit()
    monkeypatch.setattr(search_service, "get_session", factory)
    yield factory
    engine.dispose()


class TestSearchScopeFiltering:
    def test_no_scope_returns_all(self, scope_db):
        assert search_service.search_bids(allowed_prefectures=None)["total"] == 4

    def test_restricted_scope_limits_results_and_total(self, scope_db):
        result = search_service.search_bids(allowed_prefectures=["13"])
        assert sorted(r["id"] for r in result["results"]) == [1, 3]
        assert result["total"] == 2

    def test_empty_scope_returns_zero_not_unlimited(self, scope_db):
        result = search_service.search_bids(allowed_prefectures=[])
        assert result["results"] == []
        assert result["total"] == 0

    def test_scope_combines_with_user_prefecture_filter(self, scope_db):
        result = search_service.search_bids(
            prefecture=["27"], allowed_prefectures=["13"],
        )
        assert result["results"] == []
        assert result["total"] == 0

    def test_scope_respected_in_pagination(self, scope_db):
        first = search_service.search_bids(allowed_prefectures=["13"], limit=1)
        second = search_service.search_bids(
            allowed_prefectures=["13"], offset=1, limit=1,
        )
        assert [r["id"] for r in first["results"]] != [r["id"] for r in second["results"]]
        assert second["total"] == 2


class TestPrefectureOptionsScope:
    def test_empty_scope_returns_no_options(self, scope_db):
        assert search_service.get_prefectures(allowed_prefectures=[]) == []

    def test_restricted_scope_limits_options(self, scope_db):
        assert search_service.get_prefectures(allowed_prefectures=["27"]) == ["27"]

    def test_no_scope_returns_all_options(self, scope_db):
        assert search_service.get_prefectures() == ["13", "27"]


def make_api_env(monkeypatch):
    from fastapi.testclient import TestClient
    from search_api import main as api_main
    from database.models._generated import User as User_

    engine = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Bid.__table__.create(engine)
    User_.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    now = datetime(2026, 9, 17)
    with factory() as session:
        for bid_id, pref in [(1, "13"), (2, "27")]:
            session.add(Bid(
                id=bid_id, filename=f"案件{bid_id}", prefecture_code=pref,
                organization_name="東京都", analyzed_at=now, created_at=now,
                updated_at=now, current_status="新規", announcement_date=now,
            ))
        session.add(User_(
            id=7, username="regional", plan="single_region",
            allowed_prefectures='["13"]', is_active=True,
            created_at=now, subscription_status="active",
        ))
        session.commit()
    monkeypatch.setattr(api_main, "SessionLocal", factory)
    monkeypatch.setattr(api_main, "get_db_session", lambda: iter([factory()]))
    monkeypatch.setattr("services.auth_service.SessionLocal", factory, raising=False)
    client = TestClient(api_main.app)
    yield client, factory
    engine.dispose()


class TestSearchApiRegionalScopeImpl:
    @pytest.fixture
    def api_env(self, monkeypatch):
        yield from make_api_env(monkeypatch)

    def _auth_header(self, factory):
        from services.auth_service import AuthService
        from database.models._generated import User as User_
        with factory() as session:
            user = session.query(User_).get(7)
            token = AuthService(session).create_token(user)
        return {"Authorization": f"Bearer {token}"}

    def test_unauthenticated_request_is_unrestricted(self, api_env):
        client, _ = api_env
        resp = client.get("/bids")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_token_scopes_results_to_allowed_prefecture(self, api_env):
        client, factory = api_env
        resp = client.get("/bids", headers=self._auth_header(factory))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["prefecture_code"] == "13"

    def test_invalid_token_is_unrestricted(self, api_env):
        client, _ = api_env
        resp = client.get("/bids", headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_scope_applies_to_bid_detail(self, api_env):
        client, factory = api_env
        denied = client.get("/bids/2", headers=self._auth_header(factory))
        assert denied.status_code == 404
        allowed = client.get("/bids/1", headers=self._auth_header(factory))
        assert allowed.status_code == 200


class TestLegacySearchAndBidService:
    """Legacy GET /search and BidService.get_all_bids honor the scope."""

    def test_bid_service_filters_by_scope(self):
        from services.bid_service import BidService

        def make_bid(bid_id, pref):
            return SimpleNamespace(
                id=bid_id, filename=f"案件{bid_id}", project_name=None,
                source_url=None, budget=None, qualifications=None,
                deadline=None, deliverables=None, key_risks=None,
                current_status="新規", industry_category=None,
                organization_name="東京都", budget_amount=None,
                prefecture_code=pref,
            )

        repo = SimpleNamespace(list_all=lambda limit: [make_bid(1, "13"), make_bid(2, "27")])
        service = BidService(repo)
        unrestricted = service.get_all_bids()
        scoped = service.get_all_bids(allowed_prefectures=["13"])
        empty = service.get_all_bids(allowed_prefectures=[])
        assert [b["id"] for b in unrestricted] == [1, 2]
        assert [b["id"] for b in scoped] == [1]
        assert empty == []

    @pytest.fixture
    def api_env(self, monkeypatch):
        yield from make_api_env(monkeypatch)

    def _auth_header(self, factory):
        from services.auth_service import AuthService
        from database.models._generated import User as User_
        with factory() as session:
            user = session.query(User_).get(7)
            token = AuthService(session).create_token(user)
        return {"Authorization": f"Bearer {token}"}

    def test_legacy_search_scopes_results_with_token(self, api_env):
        client, factory = api_env
        resp = client.get("/search", headers=self._auth_header(factory))
        assert resp.status_code == 200
        items = resp.json()
        assert [item["id"] for item in items] == [1]

    def test_legacy_search_unauthenticated_is_unrestricted(self, api_env):
        client, _ = api_env
        resp = client.get("/search")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
