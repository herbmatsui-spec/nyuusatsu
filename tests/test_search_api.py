"""Tests for the Search API endpoints.

Uses the shared test database set up by tests/conftest.py.  Each test inserts
the data it needs via the ``db_session`` fixture (commit happens inside the
fixture's session), then issues HTTP requests through FastAPI's TestClient.
"""
from datetime import datetime
from fastapi.testclient import TestClient
import pytest

from search_api.main import app
from database.models import Bid, AwardResult
from database.models._generated import PricePrediction


@pytest.fixture
def client():
    """Fresh TestClient instance for each test."""
    return TestClient(app)


@pytest.fixture
def test_bid(db_session):
    """Insert a single Bid row and return the ORM object."""
    now = datetime.now()
    bid = Bid(
        filename="test_bid.pdf",
        source_url="https://example.com/bid/1",
        analyzed_at=now,
        budget="1000万円",
        budget_amount=10_000_000,
        qualifications="資格なし",
        deadline="2024年12月31日",
        deliverables="システム開発",
        current_status="open",
        industry_category="IT",
        organization_name="東京都",
        prefecture_code="13",
        announcement_date=datetime(2024, 7, 1),
        created_at=now,
        updated_at=now,
    )
    db_session.add(bid)
    db_session.commit()
    db_session.refresh(bid)
    return bid


@pytest.fixture
def test_award(db_session, test_bid):
    """Insert an AwardResult linked to test_bid."""
    now = datetime.now()
    award = AwardResult(
        tender_id=test_bid.id,
        source_url="https://example.com/award/1",
        agency_name="東京都",
        project_name="テスト案件",
        budget_amount=10_000_000,
        contract_amount=8_000_000,
        award_rate=0.8,
        winner_name="テスト会社",
        winner_count=1,
        announcement_date=datetime(2024, 7, 1),
        award_date=datetime(2024, 8, 1),
        created_at=now,
        updated_at=now,
        fiscal_year=2024,
        is_rebidding=False,
    )
    db_session.add(award)
    db_session.commit()
    db_session.refresh(award)
    return award


@pytest.fixture
def test_prediction(db_session, test_bid):
    """Insert a PricePrediction linked to test_bid."""
    now = datetime.now()
    pred = PricePrediction(
        bid_id=test_bid.id,
        bid_amount=10_000_000,
        expected_price=8_000_000,
        win_probability=0.8,
        rationale="テスト予測根拠",
        created_at=now,
    )
    db_session.add(pred)
    db_session.commit()
    db_session.refresh(pred)
    return pred


# ---------------------------------------------------------------------------
# Bid endpoints — Steps 3 & 4
# ---------------------------------------------------------------------------

class TestBidDetail:
    """GET /bids/{bid_id}"""

    def test_get_bid_detail_success(self, client, test_bid):
        resp = client.get(f"/bids/{test_bid.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == test_bid.id
        assert data["filename"] == "test_bid.pdf"
        assert data["organization_name"] == "東京都"
        assert data["budget_amount"] == 10_000_000
        assert data["prefecture_code"] == "13"
        assert data["current_status"] == "open"

    def test_get_bid_detail_not_found(self, client):
        resp = client.get("/bids/99999")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "HTTP_404"
        assert "not found" in body["error"]["message"].lower()

    def test_get_bid_detail_invalid_id(self, client):
        resp = client.get("/bids/abc")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"


class TestBidSearch:
    """GET /bids"""

    def test_search_bids_empty(self, client):
        resp = client.get("/bids")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0
        assert data["page"] == 1
        assert data["size"] == 20

    def test_search_bids_with_keyword(self, client, test_bid):
        resp = client.get("/bids?q=東京")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_bids_filter_by_prefecture(self, client, test_bid):
        resp = client.get("/bids?prefecture=13")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["prefecture_code"] == "13"

    def test_search_bids_filter_by_budget_range(self, client, test_bid):
        resp = client.get("/bids?budget_min=5000000&budget_max=15000000")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert 5_000_000 <= item["budget_amount"] <= 15_000_000

    def test_search_bids_pagination(self, client, test_bid):
        resp = client.get("/bids?page=1&size=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["size"] == 1
        assert len(data["items"]) <= 1

    def test_search_bids_validation_error(self, client):
        resp = client.get("/bids?page=-1")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_search_bids_empty_result_format(self, client):
        resp = client.get("/bids?q=nonexistent_keyword_12345")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["total_pages"] == 0


# ---------------------------------------------------------------------------
# Award result endpoints — Step 5
# ---------------------------------------------------------------------------

class TestAwardDetail:
    """GET /awards/{award_id}"""

    def test_get_award_detail_success(self, client, test_award):
        resp = client.get(f"/awards/{test_award.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == test_award.id
        assert data["project_name"] == "テスト案件"
        assert data["winner_name"] == "テスト会社"
        assert data["contract_amount"] == 8_000_000

    def test_get_award_detail_not_found(self, client):
        resp = client.get("/awards/99999")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "HTTP_404"


class TestAwardSearch:
    """GET /awards"""

    def test_search_awards_with_keyword(self, client, test_award):
        resp = client.get("/awards?q=テスト")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_awards_filter_by_winner(self, client, test_award):
        resp = client.get("/awards?winner_name=テスト会社")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert "テスト会社" in item["winner_name"]

    def test_search_awards_empty(self, client):
        resp = client.get("/awards?q=nonexistent_12345")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


# ---------------------------------------------------------------------------
# Forecast endpoints — Step 6
# ---------------------------------------------------------------------------

class TestForecastEndpoints:
    """GET /api/forecasts"""

    def test_list_forecasts_empty(self, client):
        resp = client.get("/api/forecasts")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 0

    def test_list_forecasts_with_pagination(self, client):
        resp = client.get("/api/forecasts?page=1&per_page=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 10


# ---------------------------------------------------------------------------
# Price prediction endpoint — Step 6 extension
# ---------------------------------------------------------------------------

class TestPricePredictions:
    """GET /price_predictions/{bid_id}"""

    def test_get_price_predictions_success(self, client, test_bid, test_prediction):
        resp = client.get(f"/price_predictions/{test_bid.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["expected_price"] == 8_000_000
        assert data[0]["win_probability"] == 0.8

    def test_get_price_predictions_no_data(self, client):
        resp = client.get("/price_predictions/99999")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Quality metrics endpoint — Step 7
# ---------------------------------------------------------------------------

class TestQualityMetrics:
    """GET /quality/metrics"""

    def test_get_quality_metrics(self, client):
        resp = client.get("/quality/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "missing_field_rate" in data
        assert "duplicate_rate" in data
        assert "coverage_rate" in data
        assert isinstance(data["missing_field_rate"], (int, float))
        assert isinstance(data["duplicate_rate"], (int, float))

    def test_get_quality_metrics_with_date(self, client):
        resp = client.get("/quality/metrics?date=2024-07-01")
        assert resp.status_code == 200
        data = resp.json()
        assert "missing_field_rate" in data


# ---------------------------------------------------------------------------
# Auth / saved search / alert endpoints — Step 8
# ---------------------------------------------------------------------------

class TestAuthEndpoints:
    """Tests for auth-protected endpoints."""

    def test_saved_searches_requires_auth(self, client):
        resp = client.get("/me/saved_searches")
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] == "HTTP_401"

    def test_saved_searches_bad_token(self, client):
        resp = client.get(
            "/me/saved_searches",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["message"] == "Invalid or expired token"

    def test_alerts_requires_auth(self, client):
        resp = client.get("/me/alerts")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Error handling — Step 9
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Verify unified error response format."""

    def test_404_error_format(self, client):
        resp = client.get("/bids/99999")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert body["error"]["code"] == "HTTP_404"

    def test_422_error_format(self, client):
        resp = client.get("/bids?page=-1")
        assert resp.status_code == 422
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Existing endpoints backward compatibility
# ---------------------------------------------------------------------------

class TestLegacyEndpoints:
    """Verify existing endpoints still work."""

    def test_search_endpoint_exists(self, client):
        resp = client.get("/search")
        assert resp.status_code == 200

    def test_normalize_endpoint_exists(self, client):
        resp = client.post(
            "/qualification/normalize",
            json={"texts": ["テスト資格"]},
        )
        assert resp.status_code in (200, 500)  # 500 if LLM keys not set

    def test_metrics_endpoint_exists(self, client):
        resp = client.get("/metrics/health")
        assert resp.status_code == 200
