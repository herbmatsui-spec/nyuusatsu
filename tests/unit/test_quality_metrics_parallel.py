"""Additional tests for QualityMetricsService - parallel processing and new features."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone
from services.quality_metrics_service import QualityMetricsService


class TestQualityMetricsParallel:
    """Tests for parallel processing features."""

    def test_collect_all_metrics_parallel(self):
        """collect_all_metrics with parallel=True should work."""
        mock_session = MagicMock()
        service = QualityMetricsService(mock_session)
        
        # Mock all individual methods
        service.missing_field_rate = MagicMock(return_value=5.0)
        service.duplicate_rate = MagicMock(return_value=2.0)
        service.acquisition_delay_median = MagicMock(return_value=30.0)
        service.coverage_rate = MagicMock(return_value=80.0)
        service.coverage_municipality_rate = MagicMock(return_value=60.0)
        service.geps_crawler_success_rate = MagicMock(return_value=95.0)
        service.geps_selector_match_rate = MagicMock(return_value=98.0)
        service.count_missing_fields = MagicMock(return_value={"budget": 50})
        service.count_duplicates = MagicMock(return_value=20)
        service.daily_delta = MagicMock(return_value={"new": 100, "updated": 50})
        
        result = service.collect_all_metrics(parallel=True)
        
        assert isinstance(result, dict)
        assert "missing_field_rate" in result
        assert "duplicate_rate" in result
        assert result["missing_field_rate"] == 5.0

    def test_collect_all_metrics_sequential(self):
        """collect_all_metrics with parallel=False should work (default)."""
        mock_session = MagicMock()
        service = QualityMetricsService(mock_session)
        
        service.missing_field_rate = MagicMock(return_value=5.0)
        service.duplicate_rate = MagicMock(return_value=2.0)
        service.acquisition_delay_median = MagicMock(return_value=30.0)
        service.coverage_rate = MagicMock(return_value=80.0)
        service.coverage_municipality_rate = MagicMock(return_value=60.0)
        service.geps_crawler_success_rate = MagicMock(return_value=95.0)
        service.geps_selector_match_rate = MagicMock(return_value=98.0)
        service.count_missing_fields = MagicMock(return_value={"budget": 50})
        service.count_duplicates = MagicMock(return_value=20)
        service.daily_delta = MagicMock(return_value={"new": 100, "updated": 50})
        
        result = service.collect_all_metrics(parallel=False)
        
        assert isinstance(result, dict)
        assert "missing_field_rate" in result
        assert result["missing_field_rate"] == 5.0

    def test_acquisition_delay_median_chunked(self):
        """acquisition_delay_median should handle large dataset with chunked approach."""
        mock_session = MagicMock()
        service = QualityMetricsService(mock_session)
        
        mock_query = MagicMock()
        service._filtered_bid_query = MagicMock(return_value=mock_query)
        
        # Large dataset: 50000 records (exceeds default chunk_size of 10000)
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 50000
        mock_query.order_by.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.scalar.return_value = 25.0
        
        result = service.acquisition_delay_median(chunk_size=10000)
        
        assert isinstance(result, float)
        assert result >= 0

    def test_acquisition_delay_median_small_dataset(self):
        """acquisition_delay_median should use simple approach for small dataset."""
        mock_session = MagicMock()
        service = QualityMetricsService(mock_session)
        
        mock_query = MagicMock()
        mock_filtered = MagicMock()
        
        # Small dataset: 100 records (even, so needs two values)
        mock_filtered.count.return_value = 100
        mock_filtered.filter.return_value = mock_filtered
        mock_filtered.order_by.return_value = mock_filtered
        mock_filtered.limit.return_value = mock_filtered
        mock_filtered.offset.return_value = mock_filtered
        mock_filtered.with_entities.return_value = mock_filtered
        mock_filtered.scalar.return_value = 30.0
        mock_filtered.all.return_value = [10.0, 20.0]  # Two values for even count
        
        # Mock the chain: session.query -> _bid_query -> _filtered_bid_query
        mock_query.filter.return_value = mock_filtered
        mock_session.query.return_value = mock_query
        service._bid_query = MagicMock(return_value=mock_filtered)

        result = service.acquisition_delay_median(chunk_size=10000)
        
        assert isinstance(result, float)
        assert result == 15.0  # Average of 10 and 20


class TestQualityMetricsMemoryMonitoring:
    """Tests for memory monitoring features."""

    def test_get_memory_usage_mb(self):
        """_get_memory_usage_mb should return float."""
        mock_session = MagicMock()
        service = QualityMetricsService(mock_session)
        
        # This may return 0.0 if psutil not available
        result = service._get_memory_usage_mb()
        assert isinstance(result, float)
        assert result >= 0

    def test_check_memory_warning_no_warning(self):
        """_check_memory_warning should not warn when under threshold."""
        mock_session = MagicMock()
        service = QualityMetricsService(mock_session)
        
        # Mock low memory usage
        service._get_memory_usage_mb = MagicMock(return_value=100.0)
        
        # Should not raise
        service._check_memory_warning("test context")


class TestQualityMetricsLogLevels:
    """Tests for log level adjustments."""

    def test_error_logging_in_methods(self, caplog):
        """Methods should log errors appropriately."""
        import logging
        caplog.set_level(logging.ERROR)
        
        mock_session = MagicMock()
        service = QualityMetricsService(mock_session)
        
        # Cause an error by making query raise
        mock_session.query.side_effect = Exception("DB error")
        
        result = service.count_missing_fields()
        
        # Should return empty dict on error
        assert result == {}
        # Should have logged error
        assert any("Error in count_missing_fields" in record.message for record in caplog.records)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])