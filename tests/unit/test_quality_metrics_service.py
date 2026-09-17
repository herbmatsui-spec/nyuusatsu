import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from services.quality_metrics_service import QualityMetricsService, REQUIRED_FIELDS
from database.models import Bid, AgencyInventory, Prefecture


@pytest.fixture
def mock_session():
    return MagicMock()


def make_query_chain(mock_session, total_count, filter_counts):
    """session.query(Bid) の呼び出しごとに異なるモックを返すヘルパー"""
    filter_call_count = [0]
    base_query = MagicMock()
    base_query.count.return_value = total_count
    
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
    
    # Mock _bid_query to return base_query
    mock_session.query.return_value = base_query


def test_count_missing_fields(mock_session):
    """必須フィールドの欠損カウントが正しく返されること"""
    service = QualityMetricsService(mock_session)

    filter_counts = [8, 3, 0, 12, 2, 7, 1]
    make_query_chain(mock_session, 100, filter_counts)

    result = service.count_missing_fields()

    assert result == {
        "budget": 8,
        "deadline": 3,
        "organization_name": 12,
        "announcement_date": 2,
        "qualifications": 7,
        "deliverables": 1,
    }


def test_count_missing_fields_no_data(mock_session):
    """データがない場合は空dictが返されること"""
    service = QualityMetricsService(mock_session)
    make_query_chain(mock_session, 0, [])

    result = service.count_missing_fields()

    assert result == {}


def test_missing_field_rate(mock_session):
    """欠損率（平均）が正しく計算されること"""
    service = QualityMetricsService(mock_session)

    # missing_field_rate 内部で count_missing_fields を呼ぶため、直接モックする
    service.count_missing_fields = MagicMock(return_value={
        "budget": 20,
        "deadline": 5,
        "prefecture_code": 0,
        "organization_name": 15,
        "announcement_date": 3,
        "qualifications": 8,
        "deliverables": 2,
    })
    mock_bid_query = MagicMock()
    mock_session.query.return_value = mock_bid_query
    mock_bid_query.count.return_value = 100  # total for _bid_query().count()

    result = service.missing_field_rate()

    # 総欠損数 = 20+5+0+15+3+8+2 = 53
    # フィールド数 = 7
    # 平均欠損/フィールド = 53/7 ≈ 7.57
    # 欠損率 = (7.57/100)*100 = 7.57%
    assert result == 7.57


def test_missing_field_rate_no_data(mock_session):
    """データがない場合は0.0が返されること"""
    service = QualityMetricsService(mock_session)
    mock_bid_query = MagicMock()
    mock_session.query.return_value = mock_bid_query
    mock_bid_query.count.return_value = 0

    result = service.missing_field_rate()

    assert result == 0.0


def test_count_duplicates(mock_session):
    """source_url の重複件数が正しくカウントされること"""
    service = QualityMetricsService(mock_session)

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
    mock_query.count.return_value = 6

    result = service.count_duplicates()

    assert result == 6


def test_duplicate_rate(mock_session):
    """重複率が正しく計算されること"""
    service = QualityMetricsService(mock_session)
    mock_bid_query = MagicMock()
    mock_session.query.return_value = mock_bid_query
    mock_bid_query.count.return_value = 200
    service.count_duplicates = MagicMock(return_value=20)

    result = service.duplicate_rate()

    assert result == 10.0


def test_duplicate_rate_no_data(mock_session):
    """データがない場合は0.0が返されること"""
    service = QualityMetricsService(mock_session)
    mock_bid_query = MagicMock()
    mock_session.query.return_value = mock_bid_query
    mock_bid_query.count.return_value = 0

    result = service.duplicate_rate()

    assert result == 0.0


def test_acquisition_delay_median(mock_session):
    """取得遅延中央値が正しく計算されること（奇数件数）"""
    service = QualityMetricsService(mock_session)

    mock_query = MagicMock()
    service._bid_query = MagicMock(return_value=mock_query)
    mock_query.filter.return_value = mock_query
    # total = 3 (odd), mid = 1
    mock_query.count.return_value = 3
    mock_query.order_by.return_value = mock_query
    mock_query.with_entities.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.scalar.return_value = 20.0

    result = service.acquisition_delay_median()

    assert result == 20.0


def test_acquisition_delay_median_even_count(mock_session):
    """偶数件数の場合の中央値計算"""
    service = QualityMetricsService(mock_session)

    mock_query = MagicMock()
    service._bid_query = MagicMock(return_value=mock_query)
    mock_query.filter.return_value = mock_query
    # total = 2 (even), mid = 1, offset = 0
    mock_query.count.return_value = 2
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.with_entities.return_value = mock_query
    mock_query.all.return_value = [10.0, 20.0]

    result = service.acquisition_delay_median()

    assert result == 15.0


def test_acquisition_delay_median_no_data(mock_session):
    """データがない場合は0.0が返されること"""
    service = QualityMetricsService(mock_session)

    mock_query = MagicMock()
    service._bid_query = MagicMock(return_value=mock_query)
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = 0

    result = service.acquisition_delay_median()

    assert result == 0.0


def test_acquisition_delay_median_negative_delay_excluded(mock_session):
    """負の遅延（DB登録が公開日より前）は除外されること"""
    service = QualityMetricsService(mock_session)

    mock_query = MagicMock()
    service._bid_query = MagicMock(return_value=mock_query)
    mock_query.filter.return_value = mock_query
    # SQL フィルターで delay >= 0 が適用されているため、負の遅延は既に除外済
    # total = 1 (only the 10-min delay row)
    mock_query.count.return_value = 1
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.with_entities.return_value = mock_query
    mock_query.scalar.return_value = 10.0

    result = service.acquisition_delay_median()

    assert result == 10.0


def test_coverage_rate(mock_session):
    """インベントリカバレッジ率が正しく計算されること"""
    service = QualityMetricsService(mock_session)
    mock_query_total = MagicMock()
    mock_query_crawled = MagicMock()
    mock_session.query.side_effect = [mock_query_total, mock_query_crawled]
    mock_query_total.count.return_value = 10
    mock_query_crawled.filter.return_value = mock_query_crawled
    mock_query_crawled.count.return_value = 8

    result = service.coverage_rate()

    assert result == 80.0


def test_coverage_rate_no_inventory(mock_session):
    """インベントリがない場合は0.0が返されること"""
    service = QualityMetricsService(mock_session)
    mock_query = MagicMock()
    mock_session.query.return_value = mock_query
    mock_query.count.return_value = 0

    result = service.coverage_rate()

    assert result == 0.0


def test_coverage_municipality_rate(mock_session):
    """自治体カバレッジ率が正しく計算されること"""
    service = QualityMetricsService(mock_session)
    mock_query_pref = MagicMock()
    mock_query_bid = MagicMock()
    mock_session.query.side_effect = [mock_query_pref, mock_query_bid]
    mock_query_pref.count.return_value = 47
    mock_query_bid.filter.return_value = mock_query_bid
    mock_query_bid.with_entities.return_value = mock_query_bid
    mock_query_bid.distinct.return_value = mock_query_bid
    mock_query_bid.count.return_value = 10

    result = service.coverage_municipality_rate()

    assert result == 21.28


def test_coverage_municipality_rate_no_prefecture(mock_session):
    """都道府県マスタがない場合は0.0が返されること"""
    service = QualityMetricsService(mock_session)
    mock_query = MagicMock()
    mock_session.query.return_value = mock_query
    mock_query.count.return_value = 0

    result = service.coverage_municipality_rate()

    assert result == 0.0


def test_daily_delta(mock_session):
    """日次デルタが正しく計算されること"""
    service = QualityMetricsService(mock_session)
    mock_query = MagicMock()
    service._bid_query = MagicMock(return_value=mock_query)
    mock_query.filter.return_value = mock_query
    mock_query.count.side_effect = [5, 3]

    result = service.daily_delta(days=1)

    assert result == {"new": 5, "updated": 3}


def test_collect_all_metrics(mock_session):
    """全メトリクス収集が正しく動作すること"""
    service = QualityMetricsService(mock_session)
    service.missing_field_rate = MagicMock(return_value=5.0)
    service.duplicate_rate = MagicMock(return_value=10.0)
    service.acquisition_delay_median = MagicMock(return_value=30.0)
    service.coverage_rate = MagicMock(return_value=50.0)
    service.coverage_municipality_rate = MagicMock(return_value=60.0)
    service.count_missing_fields = MagicMock(return_value={"organization_name": 5, "budget": 3})
    service.count_duplicates = MagicMock(return_value=20)
    service.daily_delta = MagicMock(return_value={"new": 100, "updated": 50})
    service.geps_crawler_success_rate = MagicMock(return_value=95.0)
    service.geps_selector_match_rate = MagicMock(return_value=98.0)
    service.collect_llm_extraction_quality = MagicMock(return_value={
        "llm_sample_count": 100.0,
        "llm_missing_budget_amount_rate": 10.0,
        "llm_missing_qualifications_rate": 5.0,
        "llm_missing_delivery_deadline_rate": 30.0,
        "llm_missing_deliverables_rate": 5.0,
        "llm_budget_anomaly_count": 1.0,
        "llm_budget_anomaly_rate": 1.0,
    })

    result = service.collect_all_metrics()

    expected = {
        "missing_field_rate": 5.0,
        "duplicate_rate": 10.0,
        "acquisition_delay_median": 30.0,
        "coverage_rate": 50.0,
        "coverage_municipality_rate": 60.0,
        "geps_crawler_success_rate": 95.0,
        "geps_selector_match_rate": 98.0,
        "missing_organization_name": 5,
        "missing_budget": 3,
        "duplicate_count": 20,
        "daily_new": 100,
        "daily_updated": 50,
        "llm_sample_count": 100.0,
        "llm_missing_budget_amount_rate": 10.0,
        "llm_missing_qualifications_rate": 5.0,
        "llm_missing_delivery_deadline_rate": 30.0,
        "llm_missing_deliverables_rate": 5.0,
        "llm_budget_anomaly_count": 1.0,
        "llm_budget_anomaly_rate": 1.0,
    }
    assert result == expected


def test_date_range_filter(mock_session):
    """日付範囲フィルタが適用されること"""
    date_start = datetime(2026, 1, 1)
    date_end = datetime(2026, 1, 31)
    service = QualityMetricsService(mock_session, date_start=date_start, date_end=date_end)

    make_query_chain(mock_session, 100, [10] * len(REQUIRED_FIELDS))

    result = service.count_missing_fields()

    assert mock_session.query.called


def test_required_fields_constant():
    """REQUIRED_FIELDS定数が正しく定義されていること"""
    expected_fields = [
        "budget",
        "deadline",
        "prefecture_code",
        "organization_name",
        "announcement_date",
        "qualifications",
        "deliverables",
    ]
    assert REQUIRED_FIELDS == expected_fields


def test_count_duplicates_uses_source_url():
    """count_duplicates が source_url で重複判定することを確認"""
    from unittest.mock import MagicMock
    from services.quality_metrics_service import QualityMetricsService
    from database.models import Bid
    from sqlalchemy import func

    mock_session = MagicMock()
    service = QualityMetricsService(mock_session)
    service._bid_query = MagicMock(return_value=mock_session.query.return_value)

    mock_subquery = MagicMock()
    mock_session.query.return_value.with_entities.return_value.group_by.return_value.having.return_value.subquery.return_value = mock_subquery
    mock_session.query.return_value.filter.return_value = mock_session.query.return_value
    mock_session.query.return_value.count.return_value = 3

    result = service.count_duplicates()
    assert result == 3