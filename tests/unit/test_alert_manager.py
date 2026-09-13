"""Tests for Alert Manager."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from services.alert_manager import AlertManager, send_slack_alert, send_line_alert, send_live_test_report


class TestAlertManager:
    """AlertManager のテスト。"""

    def test_init_default_threshold(self):
        """デフォルト閾値で初期化"""
        am = AlertManager()
        assert am.failure_threshold == 3
        assert am._consecutive_failures == {}

    def test_init_custom_threshold(self):
        """カスタム閾値で初期化"""
        am = AlertManager(failure_threshold=5)
        assert am.failure_threshold == 5

    def test_evaluate_and_alert_healthy(self):
        """正常状態の評価"""
        am = AlertManager()
        am.evaluate_and_alert("TestComponent", True, "All good")
        
        assert am._consecutive_failures.get("TestComponent", 0) == 0

    def test_evaluate_and_alert_first_failure(self):
        """初回失敗"""
        am = AlertManager()
        am.evaluate_and_alert("TestComponent", False, "Error occurred")
        
        assert am._consecutive_failures["TestComponent"] == 1

    def test_evaluate_and_alert_reaches_threshold(self):
        """閾値到達でカウント増加"""
        am = AlertManager()
        for i in range(3):
            am.evaluate_and_alert("TestComponent", False, f"Error {i+1}")
        
        assert am._consecutive_failures["TestComponent"] == 3

    def test_evaluate_and_alert_recovery(self):
        """復旧時にカウントリセット"""
        am = AlertManager()
        for i in range(3):
            am.evaluate_and_alert("TestComponent", False, f"Error {i+1}")
        
        am.evaluate_and_alert("TestComponent", True, "Recovered")
        
        assert am._consecutive_failures["TestComponent"] == 0

    def test_evaluate_and_alert_no_recovery_before_threshold(self):
        """閾値未満で復旧"""
        am = AlertManager()
        am.evaluate_and_alert("TestComponent", False, "Error 1")
        am.evaluate_and_alert("TestComponent", True, "Recovered")
        
        assert am._consecutive_failures["TestComponent"] == 0

    def test_multiple_components_independent(self):
        """複数コンポーネントは独立してカウント"""
        am = AlertManager()
        am.evaluate_and_alert("ComponentA", False, "Error")
        am.evaluate_and_alert("ComponentB", False, "Error")
        am.evaluate_and_alert("ComponentA", False, "Error")
        
        assert am._consecutive_failures["ComponentA"] == 2
        assert am._consecutive_failures["ComponentB"] == 1


class TestSendAlerts:
    """アラート送信関数のテスト。"""

    @patch("services.alert_manager.SlackNotificationService")
    def test_send_slack_alert(self, mock_slack_class):
        mock_service = MagicMock()
        mock_service.webhook_url = "https://hooks.slack.com/xxx"
        mock_service.send.return_value = True
        mock_slack_class.return_value = mock_service
        
        result = send_slack_alert("Test message")
        
        assert result is True
        mock_service.send.assert_called_once_with("Test message")

    @patch("services.alert_manager.SlackNotificationService")
    def test_send_slack_alert_not_configured(self, mock_slack_class):
        mock_service = MagicMock()
        mock_service.webhook_url = None
        mock_slack_class.return_value = mock_service
        
        result = send_slack_alert("Test message")
        assert result is False

    @patch("services.alert_manager.SlackNotificationService")
    def test_send_slack_alert_failure(self, mock_slack_class):
        mock_service = MagicMock()
        mock_service.webhook_url = "https://hooks.slack.com/xxx"
        mock_service.send.side_effect = Exception("Slack error")
        mock_slack_class.return_value = mock_service
        
        result = send_slack_alert("Test message")
        assert result is False

    @patch("services.alert_manager.LineNotificationService")
    def test_send_line_alert(self, mock_line_class):
        mock_service = MagicMock()
        mock_service.access_token = "token"
        mock_service.user_id = "user"
        mock_service.send.return_value = True
        mock_line_class.return_value = mock_service
        
        result = send_line_alert("Test message")
        assert result is True

    @patch("services.alert_manager.LineNotificationService")
    def test_send_line_alert_not_configured(self, mock_line_class):
        mock_service = MagicMock()
        mock_service.access_token = None
        mock_line_class.return_value = mock_service
        
        result = send_line_alert("Test message")
        assert result is False

    @patch("services.alert_manager.LineNotificationService")
    def test_send_line_alert_failure(self, mock_line_class):
        mock_service = MagicMock()
        mock_service.access_token = "token"
        mock_service.user_id = "user"
        mock_service.send.side_effect = Exception("LINE error")
        mock_line_class.return_value = mock_service
        
        result = send_line_alert("Test message")
        assert result is False

    def test_send_live_test_report_not_found(self, tmp_path):
        result = send_live_test_report(tmp_path / "nonexistent.md", 1)
        assert result == {"slack": False, "line": False}

    def test_send_live_test_report_success(self, tmp_path):
        report = tmp_path / "test_report.md"
        report.write_text("# Test Report\n- Item 1\n- Item 2\n")
        
        with patch("services.alert_manager.send_slack_alert", return_value=True) as mock_slack:
            with patch("services.alert_manager.send_line_alert", return_value=True) as mock_line:
                result = send_live_test_report(report, 0)
        
        assert result == {"slack": True, "line": True}
        mock_slack.assert_called_once()
        mock_line.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])