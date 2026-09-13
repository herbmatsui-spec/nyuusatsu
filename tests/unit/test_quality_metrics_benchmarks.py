"""Benchmarks for QualityMetricsService using pytest-benchmark."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from services.quality_metrics_service import QualityMetricsService, REQUIRED_FIELDS
from database.models import Bid


def create_mock_session_with_data(total_count: int, missing_ratios: dict = None):
    """Create a mock session with configurable data for benchmarking."""
    mock_session = MagicMock()
    
    if missing_ratios is None:
        missing_ratios = {field: 0.1 for field in REQUIRED_FIELDS}
    
    def create_base_query():
        base_query = MagicMock()
        base_query.count.return_value = total_count
        
        call_idx = [0]
        
        def filter_side_effect(*args, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            filtered_mock = MagicMock()
            
            # Simulate missing field counts based on ratios
            if idx < len(REQUIRED_FIELDS):
                field = REQUIRED_FIELDS[idx]
                missing_count = int(total_count * missing_ratios.get(field, 0.1))
                filtered_mock.count.return_value = missing_count
            else:
                filtered_mock.count.return_value = 0
            
            return filtered_mock
        
        base_query.filter.side_effect = filter_side_effect
        return base_query
    
    mock_session.query.side_effect = lambda *args, **kwargs: create_base_query()
    return mock_session


class TestQualityMetricsBenchmarks:
    """Benchmark tests for QualityMetricsService methods."""
    
    @pytest.fixture
    def small_dataset_session(self):
        """Small dataset: 1000 records."""
        return create_mock_session_with_data(1000)
    
    @pytest.fixture
    def medium_dataset_session(self):
        """Medium dataset: 10000 records."""
        return create_mock_session_with_data(10000)
    
    @pytest.fixture
    def large_dataset_session(self):
        """Large dataset: 100000 records."""
        return create_mock_session_with_data(100000)
    
    def test_count_missing_fields_benchmark(self, benchmark, small_dataset_session):
        """Benchmark count_missing_fields with small dataset."""
        service = QualityMetricsService(small_dataset_session)
        result = benchmark(service.count_missing_fields)
        assert isinstance(result, dict)
    
    def test_count_missing_fields_medium_benchmark(self, benchmark, medium_dataset_session):
        """Benchmark count_missing_fields with medium dataset."""
        service = QualityMetricsService(medium_dataset_session)
        result = benchmark(service.count_missing_fields)
        assert isinstance(result, dict)
    
    def test_missing_field_rate_benchmark(self, benchmark, small_dataset_session):
        """Benchmark missing_field_rate with small dataset."""
        service = QualityMetricsService(small_dataset_session)
        service.count_missing_fields = MagicMock(return_value={
            "budget": 100, "deadline": 50, "prefecture_code": 10,
            "organization_name": 80, "announcement_date": 20,
            "qualifications": 60, "deliverables": 30
        })
        result = benchmark(service.missing_field_rate)
        assert isinstance(result, float)
    
    def test_count_duplicates_benchmark(self, benchmark, small_dataset_session):
        """Benchmark count_duplicates with small dataset."""
        service = QualityMetricsService(small_dataset_session)
        mock_query = MagicMock()
        service._bid_query = MagicMock(return_value=mock_query)
        mock_query.filter.return_value = mock_query
        
        # Setup subquery mock
        mock_subquery = MagicMock()
        mock_query.with_entities.return_value.group_by.return_value.having.return_value.subquery.return_value = mock_subquery
        mock_query.filter.return_value.count.return_value = 50
        
        result = benchmark(service.count_duplicates)
        assert isinstance(result, int)
    
    def test_acquisition_delay_median_benchmark(self, benchmark, small_dataset_session):
        """Benchmark acquisition_delay_median with small dataset."""
        service = QualityMetricsService(small_dataset_session)
        mock_query = MagicMock()
        service._bid_query = MagicMock(return_value=mock_query)
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 100
        mock_query.order_by.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.scalar.return_value = 30.0
        
        result = benchmark(service.acquisition_delay_median)
        assert isinstance(result, float)
    
    def test_collect_all_metrics_benchmark(self, benchmark, small_dataset_session):
        """Benchmark collect_all_metrics with small dataset."""
        service = QualityMetricsService(small_dataset_session)
        
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
        
        result = benchmark(service.collect_all_metrics)
        assert isinstance(result, dict)
        assert "missing_field_rate" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])