"""Benchmark tests for QualityMetricsService using pytest-benchmark.

Run with: pytest tests/unit/test_quality_metrics_benchmark.py --benchmark-only
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from services.quality_metrics_service import QualityMetricsService, REQUIRED_FIELDS


@pytest.fixture
def mock_session():
    """Create a mock session with realistic query chain."""
    return MagicMock()


def make_realistic_mock_session(total_count=10000):
    """Create a mock session that simulates realistic database query patterns."""
    mock_session = MagicMock()

    # Track filter calls for count_missing_fields loop
    filter_call_count = [0]

    def create_base_query():
        base_query = MagicMock()
        base_query.count.return_value = total_count

        filter_counts = [total_count // 10] * len(REQUIRED_FIELDS)

        def filter_side_effect(*args, **kwargs):
            idx = filter_call_count[0]
            filter_call_count[0] += 1
            filtered_mock = MagicMock()
            if idx < len(filter_counts):
                filtered_mock.count.return_value = filter_counts[idx]
            else:
                filtered_mock.count.return_value = 0
            return filtered_mock

        base_query.filter.side_effect = filter_side_effect
        return base_query

    mock_session.query.side_effect = lambda *args, **kwargs: create_base_query()
    return mock_session


class TestQualityMetricsBenchmarks:
    """Benchmark tests for QualityMetricsService methods."""

    def test_benchmark_count_missing_fields(self, benchmark):
        """Benchmark count_missing_fields with 10k records."""
        mock_session = make_realistic_mock_session(10000)
        service = QualityMetricsService(mock_session)

        def run():
            return service.count_missing_fields()

        result = benchmark(run)
        assert isinstance(result, dict)

    def test_benchmark_missing_field_rate(self, benchmark):
        """Benchmark missing_field_rate with 10k records."""
        mock_session = make_realistic_mock_session(10000)
        service = QualityMetricsService(mock_session)

        def run():
            return service.missing_field_rate()

        result = benchmark(run)
        assert isinstance(result, float)

    def test_benchmark_count_duplicates(self, benchmark):
        """Benchmark count_duplicates with 10k records."""
        total_count = 10000
        mock_session = make_realistic_mock_session(total_count)
        service = QualityMetricsService(mock_session)

        def create_mock():
            mock_query = MagicMock()
            mock_session.query.return_value = mock_query

            mock_subquery = MagicMock()
            mock_subq_query = MagicMock()
            mock_query.with_entities.return_value.group_by.return_value.having.return_value.subquery.return_value = mock_subquery
            mock_session.query.return_value = mock_subq_query

            call_count = [0]
            def bid_query_side_effect():
                call_count[0] += 1
                return mock_query if call_count[0] == 1 else mock_query
            service._bid_query = MagicMock(side_effect=bid_query_side_effect)

            mock_query.with_entities.return_value.group_by.return_value.having.return_value.subquery.return_value = mock_subquery
            mock_session.query.return_value = mock_subq_query
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = total_count // 100  # 1% duplicates

        create_mock()

        result = benchmark(lambda: service.count_duplicates())
        assert isinstance(result, int)

    def test_benchmark_acquisition_delay_median(self, benchmark):
        """Benchmark acquisition_delay_median with 10k records."""
        mock_session = make_realistic_mock_session(10000)
        service = QualityMetricsService(mock_session)

        def create_mock():
            mock_query = MagicMock()
            service._bid_query = MagicMock(return_value=mock_query)
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 10000
            mock_query.order_by.return_value = mock_query
            mock_query.with_entities.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.offset.return_value = mock_query
            mock_query.scalar.return_value = 20.0

        create_mock()

        result = benchmark(lambda: service.acquisition_delay_median())
        assert isinstance(result, float)

    def test_benchmark_coverage_rate(self, benchmark):
        """Benchmark coverage_rate with 10k records."""
        mock_session = MagicMock()
        service = QualityMetricsService(mock_session)

        mock_query_total = MagicMock()
        mock_query_crawled = MagicMock()
        mock_session.query.side_effect = [mock_query_total, mock_query_crawled]
        mock_query_total.count.return_value = 10000
        mock_query_crawled.filter.return_value = mock_query_crawled
        mock_query_crawled.count.return_value = 8000

        result = benchmark(lambda: service.coverage_rate())
        assert isinstance(result, float)

    def test_benchmark_coverage_municipality_rate(self, benchmark):
        """Benchmark coverage_municipality_rate with 10k records."""
        mock_session = MagicMock()
        service = QualityMetricsService(mock_session)

        mock_query_pref = MagicMock()
        mock_query_bid = MagicMock()
        mock_session.query.side_effect = [mock_query_pref, mock_query_bid]
        mock_query_pref.count.return_value = 47
        mock_query_bid.filter.return_value = mock_query_bid
        mock_query_bid.with_entities.return_value = mock_query_bid
        mock_query_bid.distinct.return_value = mock_query_bid
        mock_query_bid.count.return_value = 30

        result = benchmark(lambda: service.coverage_municipality_rate())
        assert isinstance(result, float)

    def test_benchmark_collect_all_metrics(self, benchmark):
        """Benchmark collect_all_metrics with mocked sub-methods."""
        mock_session = MagicMock()
        service = QualityMetricsService(mock_session)

        # Mock all sub-methods to avoid actual DB calls
        service.missing_field_rate = MagicMock(return_value=5.0)
        service.duplicate_rate = MagicMock(return_value=10.0)
        service.acquisition_delay_median = MagicMock(return_value=30.0)
        service.coverage_rate = MagicMock(return_value=50.0)
        service.coverage_municipality_rate = MagicMock(return_value=60.0)
        service.count_missing_fields = MagicMock(return_value={"organization_name": 50, "budget": 30})
        service.count_duplicates = MagicMock(return_value=100)
        service.daily_delta = MagicMock(return_value={"new": 100, "updated": 50})
        service.geps_crawler_success_rate = MagicMock(return_value=95.0)
        service.geps_selector_match_rate = MagicMock(return_value=98.0)

        result = benchmark(lambda: service.collect_all_metrics())
        assert isinstance(result, dict)
        assert len(result) > 10


class TestQualityMetricsLargeDataBenchmarks:
    """Benchmarks with larger datasets to test scalability."""

    @pytest.mark.parametrize("record_count", [1000, 10000, 50000])
    def test_benchmark_count_missing_fields_scaling(self, benchmark, record_count):
        """Benchmark count_missing_fields with varying record counts."""
        mock_session = make_realistic_mock_session(record_count)
        service = QualityMetricsService(mock_session)

        def run():
            return service.count_missing_fields()

        benchmark.extra_info["record_count"] = record_count
        result = benchmark(run)
        assert isinstance(result, dict)

    @pytest.mark.parametrize("record_count", [1000, 10000, 50000])
    def test_benchmark_acquisition_delay_median_scaling(self, benchmark, record_count):
        """Benchmark acquisition_delay_median with varying record counts."""
        mock_session = make_realistic_mock_session(record_count)
        service = QualityMetricsService(mock_session)

        def create_mock():
            mock_query = MagicMock()
            service._bid_query = MagicMock(return_value=mock_query)
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = record_count
            mock_query.order_by.return_value = mock_query
            mock_query.with_entities.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.offset.return_value = mock_query
            mock_query.scalar.return_value = 20.0

        create_mock()

        benchmark.extra_info["record_count"] = record_count
        result = benchmark(lambda: service.acquisition_delay_median())
        assert isinstance(result, float)

    @pytest.mark.parametrize("record_count", [1000, 10000, 50000])
    def test_benchmark_collect_all_metrics_scaling(self, benchmark, record_count):
        """Benchmark collect_all_metrics with varying record counts."""
        mock_session = make_realistic_mock_session(record_count)
        service = QualityMetricsService(mock_session)

        # Mock all sub-methods
        service.missing_field_rate = MagicMock(return_value=5.0)
        service.duplicate_rate = MagicMock(return_value=10.0)
        service.acquisition_delay_median = MagicMock(return_value=30.0)
        service.coverage_rate = MagicMock(return_value=50.0)
        service.coverage_municipality_rate = MagicMock(return_value=60.0)
        service.count_missing_fields = MagicMock(return_value={"organization_name": 50, "budget": 30})
        service.count_duplicates = MagicMock(return_value=100)
        service.daily_delta = MagicMock(return_value={"new": 100, "updated": 50})
        service.geps_crawler_success_rate = MagicMock(return_value=95.0)
        service.geps_selector_match_rate = MagicMock(return_value=98.0)

        benchmark.extra_info["record_count"] = record_count
        result = benchmark(lambda: service.collect_all_metrics())
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "--benchmark-only", "-v"])