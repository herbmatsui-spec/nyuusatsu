import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from database.models.procurement_forecast import ProcurementForecast
from database.models.forecast_status import ForecastStatusEnum
from repositories.forecast_repository import ForecastRepository


class TestForecastRepository:
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        return session

    @pytest.fixture
    def repository(self, mock_session):
        return ForecastRepository(mock_session)

    @pytest.fixture
    def sample_forecast_data(self):
        return {
            "agency_id": 1,
            "fiscal_year": 2026,
            "quarter": 2,
            "title": "道路維持管理業務",
            "description": "市道の維持管理を行います",
            "estimated_budget": "5000万円",
            "estimated_budget_amount": 50000000,
            "category": "土木",
            "industry_category": "建設",
            "source_url": "https://example.go.jp/forecast/123",
            "status": "draft",
        }

    def test_create(self, repository, mock_session, sample_forecast_data):
        mock_forecast = ProcurementForecast(id=1, **sample_forecast_data)
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        mock_session.refresh = MagicMock()

        with patch.object(repository, 'session', mock_session):
            with patch('repositories.forecast_repository.ProcurementForecast', return_value=mock_forecast):
                result = repository.create(sample_forecast_data)

                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()
                mock_session.refresh.assert_called_once()

    def test_get_by_id(self, repository, mock_session):
        mock_forecast = ProcurementForecast(id=1, title="Test Forecast")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_forecast
        mock_session.query.return_value = mock_query

        with patch.object(repository, 'session', mock_session):
            result = repository.get_by_id(1)

        assert result == mock_forecast
        mock_query.filter.assert_called_once()

    def test_get_active(self, repository, mock_session):
        mock_forecasts = [
            ProcurementForecast(id=1, title="Forecast 1", status="published"),
            ProcurementForecast(id=2, title="Forecast 2", status="draft"),
        ]
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_forecasts
        mock_session.query.return_value = mock_query

        with patch.object(repository, 'session', mock_session):
            result = repository.get_active()

        assert len(result) == 2
        mock_session.query.assert_called_once()

    def test_search(self, repository, mock_session):
        mock_forecasts = [
            ProcurementForecast(id=1, title="道路工事"),
        ]
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_forecasts
        mock_session.query.return_value = mock_query

        with patch.object(repository, 'session', mock_session):
            result = repository.search("道路")

        assert len(result) == 1
        assert "道路" in result[0].title

    def test_update_status(self, repository, mock_session):
        mock_forecast = ProcurementForecast(
            id=1,
            title="Test",
            status="draft"
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_forecast
        mock_session.query.return_value = mock_query
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        mock_session.refresh = MagicMock()

        with patch.object(repository, 'session', mock_session):
            result = repository.update_status(1, "published", "Test memo")

        assert result.status == "published"
        mock_session.commit.assert_called()

    def test_count_by_status(self, repository, mock_session):
        mock_query = MagicMock()
        mock_query.filter.return_value.count.return_value = 5
        mock_session.query.return_value = mock_query

        with patch.object(repository, 'session', mock_session):
            result = repository.count_by_status("published")

        assert result == 5