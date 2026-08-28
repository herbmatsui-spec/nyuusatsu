import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from database.models.procurement_forecast import ProcurementForecast, ForecastStatus
from repositories.forecast_repository import ForecastRepository
from services.forecast_validator import ForecastValidator
from services.forecast_dedup_service import ForecastDedupService
from services.forecast_batch_service import ForecastBatchService


class TestForecastPipeline:
    """発注見通しパイプラインの結合テスト（モックベース）。"""

    @pytest.fixture
    def session(self):
        return MagicMock()

    def test_validator_fills_fiscal_year(self):
        validator = ForecastValidator()
        result = validator.validate({"title": "テスト工事", "fiscal_year": None})
        assert result["is_valid"] is True
        assert isinstance(result["data"]["fiscal_year"], int)

    def test_dedup_detects_duplicate(self):
        session = MagicMock()
        existing = ProcurementForecast(id=1, agency_id=1, title="同じ案件", fiscal_year=2026)
        session.query.return_value.filter.return_value.all.return_value = [existing]
        dedup = ForecastDedupService(session)
        dup = dedup.find_duplicate(1, "同じ案件", 2026)
        assert dup is not None
        assert dup.id == 1

    def test_batch_save_new_and_update(self):
        session = MagicMock()
        # 初回は既存なし -> 新規作成
        session.query.return_value.filter.return_value.first.return_value = None
        batch = ForecastBatchService(session)
        saved = batch.save_forecasts(1, [{"title": "新規案件", "fiscal_year": 2026, "status": "draft"}])
        assert len(saved) == 1
        session.add.assert_called()
        session.commit.assert_called()

    def test_pipeline_extract_then_validate(self):
        from services.forecast_data_extractor import ForecastDataExtractor
        extractor = ForecastDataExtractor()
        text = "件名: 道路改良工事\n予算: 3,000万円\n公示: 2026-04-01\n土木"
        data = extractor.extract_structured_data(text)
        assert data["title"] == "道路改良工事"
        assert data["estimated_budget_amount"] == 30000000
        assert data["expected_publish_date"] == "2026-04-01"
        assert data["category"] == "土木"

        validator = ForecastValidator()
        result = validator.validate(data)
        assert result["is_valid"] is True

    @patch("scheduler_jobs.forecast_crawl_job.asyncio.run")
    def test_crawl_all_forecasts_runs(self, mock_run):
        # asyncio.run をモックしてスケジューラ呼び出しを検証
        mock_run.return_value = {"agency": "Test", "found": 1, "stored": 1}
        from scheduler_jobs.forecast_crawl_job import crawl_agency_forecasts
        with patch("scheduler_jobs.forecast_crawl_job.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_agency = MagicMock()
            mock_agency.id = 1
            mock_agency.name = "Test"
            mock_agency.base_url = "https://example.jp"
            mock_agency.type = "municipality"
            mock_session.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_agency
            mock_get_db.return_value = mock_session
            result = crawl_agency_forecasts(1)
            assert result["stored"] == 1
