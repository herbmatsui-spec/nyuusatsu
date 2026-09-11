import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from services.quality_metrics_service import QualityMetricsService
from services.quality_alert_service import QualityAlertService
from database.models import Bid, QualityMetric, QualityAlert


@pytest.fixture
def mock_redis():
    with patch("services.quality_alert_service.redis_conn") as mock_redis:
        mock_redis.exists.return_value = False  # No duplicate alert today
        mock_redis.setex.return_value = True
        yield mock_redis


@pytest.fixture
def mock_slack_line():
    with patch("services.quality_alert_service.QualityAlertService._send_slack_alert") as mock_slack, \
         patch("services.quality_alert_service.QualityAlertService._send_line_alert") as mock_line:
        mock_slack.return_value = True
        mock_line.return_value = True
        yield mock_slack, mock_line


def test_quality_metrics_alert_flow(db_session, mock_redis, mock_slack_line):
    """Integration test for quality metrics collection and alert evaluation."""
    # Setup: Insert a Bid with missing organization_name to trigger missing_field_rate alert
    now = datetime.utcnow()
    bid = Bid(
        filename="test.pdf",
        source_url="http://example.com/test",
        analyzed_at=now,
        organization_name=None,  # This will cause missing field
        budget="1000000",
        deadline=datetime(2026, 12, 31),
        prefecture_code="13",
        announcement_date=datetime(2026, 1, 1),
        created_at=now,
        updated_at=now,
        current_status="active",
    )
    db_session.add(bid)
    db_session.commit()

    # Create quality tables
    from database.engine import engine
    from database.models import create_all_quality_tables
    create_all_quality_tables(engine)

    # Step 1: Collect quality metrics and save to database
    service = QualityMetricsService(db_session)
    metrics = service.collect_all_metrics()
    # Save metrics to quality_metric table (mimicking the collect script)
    for metric_name, value in metrics.items():
        if isinstance(value, (int, float)):
            qm = QualityMetric(
                metric_name=metric_name,
                value=float(value),
                recorded_at=datetime.utcnow(),
            )
            db_session.add(qm)
    db_session.commit()

    # Step 2: Evaluate alerts and send notifications
    alert_service = QualityAlertService(db_session)
    # We'll test one metric that we know will exceed the threshold: missing_field_rate
    # Set up thresholds so that missing_field_rate > 0 triggers an alert.
    # We'll monkeypatch the threshold loading in the alert service to return low thresholds.
    mock_slack, mock_line = mock_slack_line
    with patch("services.quality_alert_service._load_yaml_thresholds") as mock_load_thresholds:
        mock_load_thresholds.return_value = {
            "missing_field_rate": {
                "warning": 0.0,  # Any value >= 0.0 triggers warning
                "critical": 10.0,  # Value >= 10.0 triggers alert
                "lower_is_worse": False,
            }
        }
        # Now evaluate the missing_field_rate metric
        missing_field_rate = metrics.get("missing_field_rate", 0.0)
        print(f"metrics: {metrics}")
        print(f"missing_field_rate: {missing_field_rate}")
        # The alert service's send_alert method is called by the evaluation script.
        # We'll call it directly for this metric.
        # But note: the evaluation script checks all metrics. We'll just test that our metric triggers an alert.
        level = None
        if missing_field_rate >= 10.0:
            level = "alert"
        elif missing_field_rate >= 0.0:
            level = "warn"
        if level:
            # Send alert
            result = alert_service.send_alert("missing_field_rate", missing_field_rate, level)
            assert result is True, "Alert should be sent"

    # Step 3: Verify that an alert was saved in the database
    alerts = db_session.query(QualityAlert).filter_by(metric="missing_field_rate").all()
    assert len(alerts) == 1, "One alert should be saved"
    alert = alerts[0]
    assert alert.level == level
    assert alert.value == missing_field_rate
    # Check that the threshold is correct (should be the warning or critical threshold we set)
    if level == "warn":
        assert alert.threshold == 0.0
    else:
        assert alert.threshold == 10.0

    # Step 4: Verify that Slack and LINE notifications were mocked (called)
    assert mock_slack.called, "Slack notification should be called"
    assert mock_line.called, "LINE notification should be called"