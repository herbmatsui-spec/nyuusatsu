"""Step 11: Benchmarks for quality metrics service methods.

Uses pytest-benchmark for performance measurement.
"""

import pytest
from datetime import datetime, timedelta

from services.quality_metrics_service import QualityMetricsService


@pytest.fixture
def service_with_data(db_session):
    """Service with a small dataset for benchmarking."""
    from database.models import Bid
    
    base_time = datetime.utcnow()
    for i in range(100):
        bid = Bid(
            filename=f"bid-{i}.pdf",
            source_url=f"https://example.com/bid-{i}",
            organization_name="Test Org",
            prefecture_code=str(i % 47),
            budget=1000000 + i * 1000,
            deadline=base_time + timedelta(days=30),
            announcement_date=base_time - timedelta(days=i),
            qualifications="test",
            deliverables="test deliverables",
            current_status="active",
            analyzed_at=base_time,
            created_at=base_time - timedelta(days=i),
            updated_at=base_time - timedelta(days=i),
        )
        db_session.add(bid)
    db_session.commit()
    return QualityMetricsService(db_session)


@pytest.mark.benchmark(
    group="quality_metrics",
    min_rounds=5,
    max_time=30,
)
class TestQualityMetricsBenchmarks:
    """Benchmark tests for quality metrics collection methods."""

    def test_benchmark_count_missing_fields(self, service_with_data, benchmark):
        result = benchmark(service_with_data.count_missing_fields)
        assert isinstance(result, dict)

    def test_benchmark_missing_field_rate(self, service_with_data, benchmark):
        result = benchmark(service_with_data.missing_field_rate)
        assert isinstance(result, float)

    def test_benchmark_count_duplicates(self, service_with_data, benchmark):
        result = benchmark(service_with_data.count_duplicates)
        assert isinstance(result, int)

    def test_benchmark_duplicate_rate(self, service_with_data, benchmark):
        result = benchmark(service_with_data.duplicate_rate)
        assert isinstance(result, float)

    def test_benchmark_coverage_rate(self, service_with_data, benchmark):
        result = benchmark(service_with_data.coverage_rate)
        assert isinstance(result, float)

    def test_benchmark_collect_all_metrics_sequential(self, service_with_data, benchmark):
        result = benchmark(service_with_data.collect_all_metrics, parallel=False)
        assert isinstance(result, dict)

    @pytest.mark.skipif(True, reason="Requires async DB session support")
    def test_benchmark_collect_all_metrics_parallel(self, service_with_data, benchmark):
        result = benchmark(service_with_data.collect_all_metrics, parallel=True)
        assert isinstance(result, dict)
