"""Tests for Quality Alert Service."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, date
from services.quality_alert_service import (
    QualityAlertService,
    _load_yaml_thresholds,
    _evaluate_value,
)
from notifier import (
    SlackNotificationService,
    LineNotificationService,
    create_notification_service,
)


class TestLoadYamlThresholds:
    """_load_yaml_thresholds のテスト。"""

    def test_load_existing_file(self, tmp_path):
        """存在するYAMLファイルを読み込み"""
        yaml_file = tmp_path / "thresholds.yaml"
        yaml_file.write_text("""
metrics:
  test_metric:
    warning: 80
    critical: 90
    lower_is_worse: false
""")
        result = _load_yaml_thresholds(str(yaml_file))
        assert "test_metric" in result
        assert result["test_metric"]["warning"] == 80
        assert result["test_metric"]["critical"] == 90

    def test_load_nonexistent_file(self):
        """存在しないファイル"""
        result = _load_yaml_thresholds("/nonexistent/path.yaml")
        assert result == {}

    def test_load_invalid_yaml(self, tmp_path):
        """無効なYAML"""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("invalid: yaml: [")
        result = _load_yaml_thresholds(str(yaml_file))
        assert result == {}


class TestEvaluateValue:
    """_evaluate_value のテスト。"""

    @pytest.fixture
    def thresholds(self):
        return {
            "metric_high_bad": {
                "warning": 80,
                "critical": 90,
                "lower_is_worse": False
            },
            "metric_low_bad": {
                "warning": 20,
                "critical": 10,
                "lower_is_worse": True
            },
            "metric_warn_only": {
                "warning": 50,
                "critical": None,
                "lower_is_worse": False
            },
            "metric_alert_only": {
                "warning": None,
                "critical": 95,
                "lower_is_worse": False
            },
        }

    def test_high_bad_alert(self, thresholds):
        """上限超過でアラート"""
        level, threshold = _evaluate_value("metric_high_bad", 95, thresholds)
        assert level == "alert"
        assert threshold == 90

    def test_high_bad_warn(self, thresholds):
        """上限警告"""
        level, threshold = _evaluate_value("metric_high_bad", 85, thresholds)
        assert level == "warn"
        assert threshold == 80

    def test_high_bad_ok(self, thresholds):
        """正常"""
        level, threshold = _evaluate_value("metric_high_bad", 70, thresholds)
        assert level == "ok"
        assert threshold is None

    def test_low_bad_alert(self, thresholds):
        """下限超過でアラート"""
        level, threshold = _evaluate_value("metric_low_bad", 5, thresholds)
        assert level == "alert"
        assert threshold == 10

    def test_low_bad_warn(self, thresholds):
        """下限警告"""
        level, threshold = _evaluate_value("metric_low_bad", 15, thresholds)
        assert level == "warn"
        assert threshold == 20

    def test_low_bad_ok(self, thresholds):
        """正常"""
        level, threshold = _evaluate_value("metric_low_bad", 30, thresholds)
        assert level == "ok"

    def test_warn_only_warn(self, thresholds):
        """警告のみ設定"""
        level, threshold = _evaluate_value("metric_warn_only", 60, thresholds)
        assert level == "warn"

    def test_warn_only_ok(self, thresholds):
        """警告のみ設定で正常"""
        level, threshold = _evaluate_value("metric_warn_only", 40, thresholds)
        assert level == "ok"

    def test_alert_only_alert(self, thresholds):
        """アラートのみ設定"""
        level, threshold = _evaluate_value("metric_alert_only", 96, thresholds)
        assert level == "alert"

    def test_alert_only_ok(self, thresholds):
        """アラートのみ設定で正常"""
        level, threshold = _evaluate_value("metric_alert_only", 90, thresholds)
        assert level == "ok"

    def test_missing_metric(self, thresholds):
        """未定義メトリクス"""
        level, threshold = _evaluate_value("unknown_metric", 100, thresholds)
        assert level == "ok"
        assert threshold is None

    def test_empty_thresholds(self):
        """空のしきい値"""
        level, threshold = _evaluate_value("any_metric", 100, {})
        assert level == "ok"
        assert threshold is None


class TestQualityAlertService:
    """QualityAlertService のテスト。"""

    @pytest.fixture
    def mock_session(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_session):
        """Test service with mocked YAML thresholds"""
        with patch("services.quality_alert_service._load_yaml_thresholds") as mock_load:
            mock_load.return_value = {
                "missing_field_rate": {
                    "warning": 10.0,
                    "critical": 20.0,
                    "lower_is_worse": False
                },
                "duplicate_rate": {
                    "warning": 5.0,
                    "critical": 10.0,
                    "lower_is_worse": False
                },
            }
            svc = QualityAlertService(mock_session)
            # Force the cached property to use our mock data
            svc._yaml_thresholds = {
                "missing_field_rate": {
                    "warning": 10.0,
                    "critical": 20.0,
                    "lower_is_worse": False
                },
                "duplicate_rate": {
                    "warning": 5.0,
                    "critical": 10.0,
                    "lower_is_worse": False
                },
            }
            return svc

    def test_init(self, service):
        assert service.session is not None
        assert "missing_field_rate" in service.yaml_thresholds

    def test_evaluate_yaml_warn(self, service):
        """YAMLしきい値で警告"""
        result = service.evaluate("missing_field_rate", 15.0)
        assert result == "warn"

    def test_evaluate_yaml_alert(self, service):
        """YAMLしきい値でアラート"""
        result = service.evaluate("missing_field_rate", 25.0)
        assert result == "alert"

    def test_evaluate_yaml_ok(self, service):
        """YAMLしきい値で正常"""
        # DB fallback should return None so overall result is "ok"
        service.session.query.return_value.filter_by.return_value.first.return_value = None
        result = service.evaluate("missing_field_rate", 5.0)
        assert result == "ok"

    def test_evaluate_db_fallback(self, service):
        """DBフォールバック評価"""
        mock_threshold = MagicMock()
        mock_threshold.alert_at = 50.0
        mock_threshold.warn_at = 30.0
        mock_threshold.lower_is_worse = False
        
        service.session.query.return_value.filter_by.return_value.first.return_value = mock_threshold
        
        result = service.evaluate("unknown_metric", 60.0)
        assert result == "alert"

    def test_evaluate_db_fallback_warn(self, service):
        """DBフォールバックで警告"""
        mock_threshold = MagicMock()
        mock_threshold.alert_at = 50.0
        mock_threshold.warn_at = 30.0
        mock_threshold.lower_is_worse = False
        
        service.session.query.return_value.filter_by.return_value.first.return_value = mock_threshold
        
        result = service.evaluate("unknown_metric", 40.0)
        assert result == "warn"

    def test_evaluate_db_fallback_lower_is_worse(self, service):
        """DBフォールバック lower_is_worse=True"""
        mock_threshold = MagicMock()
        mock_threshold.alert_at = 10.0
        mock_threshold.warn_at = 20.0
        mock_threshold.lower_is_worse = True
        
        service.session.query.return_value.filter_by.return_value.first.return_value = mock_threshold
        
        result = service.evaluate("unknown_metric", 5.0)
        assert result == "alert"

    def test_evaluate_db_fallback_no_threshold(self, service):
        """DBフォールバックで閾値なし"""
        service.session.query.return_value.filter_by.return_value.first.return_value = None
        
        result = service.evaluate("unknown_metric", 100.0)
        assert result == "ok"

    def test_get_threshold_value_yaml(self, service):
        """YAMLから閾値取得 - missing_field_rate has warning=10.0, critical=20.0"""
        val = service._get_threshold_value("missing_field_rate", "alert")
        assert val == 20.0

    def test_get_threshold_value_warn(self, service):
        val = service._get_threshold_value("missing_field_rate", "warn")
        assert val == 10.0

    @patch("services.quality_alert_service.redis_conn")
    def test_check_redis_dedupe_first(self, mock_redis, service):
        """初回チェック"""
        mock_redis.exists.return_value = False
        mock_redis.setex.return_value = True
        
        result = service._check_redis_dedupe("test_metric")
        assert result is True
        mock_redis.setex.assert_called_once()

    @patch("services.quality_alert_service.redis_conn")
    def test_check_redis_dedupe_duplicate(self, mock_redis, service):
        """重複チェック"""
        mock_redis.exists.return_value = True
        
        result = service._check_redis_dedupe("test_metric")
        assert result is False

    @patch("services.quality_alert_service.redis_conn")
    def test_check_redis_dedupe_error(self, mock_redis, service):
        """Redisエラー時は通過"""
        mock_redis.exists.side_effect = Exception("Redis error")
        
        result = service._check_redis_dedupe("test_metric")
        assert result is True

    @patch("notifier.SlackNotificationService")
    def test_send_slack_alert_configured(self, mock_slack_class, service):
        """Slack設定あり"""
        mock_service = MagicMock()
        mock_service.webhook_url = "https://hooks.slack.com/xxx"
        mock_service.send.return_value = True
        mock_slack_class.return_value = mock_service
        
        result = service._send_slack_alert("Test message")
        assert result is True

    @patch("notifier.SlackNotificationService")
    def test_send_slack_alert_not_configured(self, mock_slack_class, service):
        """Slack未設定"""
        mock_service = MagicMock()
        mock_service.webhook_url = None
        mock_service.send.return_value = False
        mock_slack_class.return_value = mock_service
        
        result = service._send_slack_alert("Test message")
        assert result is False

    @patch("notifier.LineNotificationService")
    def test_send_line_alert_configured(self, mock_line_class, service):
        """LINE設定あり"""
        mock_service = MagicMock()
        mock_service.access_token = "token"
        mock_service.user_id = "user"
        mock_service.send.return_value = True
        mock_line_class.return_value = mock_service
        
        result = service._send_line_alert("Test message")
        assert result is True

    @patch("notifier.LineNotificationService")
    def test_send_line_alert_not_configured(self, mock_line_class, service):
        """LINE未設定"""
        mock_service = MagicMock()
        mock_service.access_token = None
        mock_service.send.return_value = False
        mock_line_class.return_value = mock_service
        
        result = service._send_line_alert("Test message")
        assert result is False

    @patch.object(QualityAlertService, "_check_redis_dedupe", return_value=True)
    @patch.object(QualityAlertService, "_send_slack_alert", return_value=True)
    @patch.object(QualityAlertService, "_send_line_alert", return_value=True)
    def test_send_alert_success(self, mock_line, mock_slack, mock_dedupe, service):
        """アラート送信成功"""
        result = service.send_alert("test_metric", 25.0, "alert")
        assert result is True
        assert service.session.add.called
        assert service.session.commit.called

    @patch.object(QualityAlertService, "_check_redis_dedupe", return_value=False)
    def test_send_alert_dedupe(self, mock_dedupe, service):
        """重複抑制"""
        result = service.send_alert("test_metric", 25.0, "alert")
        assert result is False

    def test_send_alert_invalid_level(self, service):
        """無効なレベル"""
        result = service.send_alert("test_metric", 25.0, "invalid")
        assert result is False

    @patch.object(QualityAlertService, "_check_redis_dedupe", return_value=True)
    @patch.object(QualityAlertService, "_send_slack_alert", return_value=False)
    @patch.object(QualityAlertService, "_send_line_alert", return_value=False)
    def test_send_alert_both_failed(self, mock_line, mock_slack, mock_dedupe, service):
        """両方失敗"""
        result = service.send_alert("test_metric", 25.0, "alert")
        assert result is False

    def test_get_recent_alerts(self, service):
        """最近のアラート取得"""
        mock_alerts = [MagicMock(), MagicMock()]
        service.session.query.return_value.order_by.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = mock_alerts
        
        result = service.get_recent_alerts(limit=10, level="alert", metric="test", start_date=datetime.now(), end_date=datetime.now())
        
        assert result == mock_alerts


class TestSendAlerts:
    """スタンドアロン送信関数のテスト。"""

    @patch("notifier.create_notification_service")
    def test_send_slack_alert(self, mock_create):
        mock_service = MagicMock()
        mock_service.send.return_value = True
        mock_create.return_value = mock_service
        
        from services.alert_manager import send_slack_alert
        result = send_slack_alert("Test message")
        assert result is True

    @patch("notifier.create_notification_service")
    def test_send_slack_alert_failure(self, mock_create):
        mock_service = MagicMock()
        mock_service.send.side_effect = Exception("Error")
        mock_create.return_value = mock_service
        
        from services.alert_manager import send_slack_alert
        result = send_slack_alert("Test message")
        assert result is False

    @patch("notifier.create_notification_service")
    def test_send_line_alert(self, mock_create):
        mock_service = MagicMock()
        mock_service.send.return_value = True
        mock_create.return_value = mock_service
        
        from services.alert_manager import send_line_alert
        result = send_line_alert("Test message")
        assert result is True

    def test_send_live_test_report_not_found(self, tmp_path):
        from services.alert_manager import send_live_test_report
        result = send_live_test_report(tmp_path / "nonexistent.md", 1)
        assert result == {"slack": False, "line": False}

    def test_send_live_test_report_success(self, tmp_path):
        from services.alert_manager import send_live_test_report
        report = tmp_path / "test.md"
        report.write_text("# Report\n- Item 1\n")
        
        with patch("services.alert_manager.send_slack_alert", return_value=True) as mock_slack:
            with patch("services.alert_manager.send_line_alert", return_value=True) as mock_line:
                result = send_live_test_report(report, 0)
        
        assert result == {"slack": True, "line": True}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])