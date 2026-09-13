"""Tests for Health Checker."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from services.health_checker import (
    HealthChecker,
    HealthStatus,
    ComponentHealth,
)


class TestHealthStatus:
    """HealthStatus enum のテスト。"""

    def test_values(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestComponentHealth:
    """ComponentHealth データクラスのテスト。"""

    def test_creation(self):
        ch = ComponentHealth("Test", HealthStatus.HEALTHY, "OK")
        assert ch.name == "Test"
        assert ch.status == HealthStatus.HEALTHY
        assert ch.message == "OK"

    def test_to_dict(self):
        ch = ComponentHealth("Test", HealthStatus.HEALTHY, "OK", details={"key": "value"})
        result = ch.to_dict()
        
        assert result["name"] == "Test"
        assert result["status"] == "healthy"
        assert result["message"] == "OK"
        assert result["details"] == {"key": "value"}
        assert "last_checked" in result


class TestHealthChecker:
    """HealthChecker のテスト。"""

    @pytest.fixture
    def health_checker(self):
        return HealthChecker(queue_alert_threshold=100)

    @pytest.fixture
    def health_checker_low_threshold(self):
        return HealthChecker(queue_alert_threshold=10)

    # Redis チェック
    @patch("database.redis_conn.redis_conn")
    def test_check_redis_success(self, mock_redis_conn):
        mock_redis_conn.ping.return_value = True
        
        hc = HealthChecker()
        result = hc.check_redis()
        
        assert result.name == "Redis"
        assert result.status == HealthStatus.HEALTHY
        mock_redis_conn.ping.assert_called_once()

    @patch("database.redis_conn.redis_conn")
    def test_check_redis_failure(self, mock_redis_conn):
        mock_redis_conn.ping.side_effect = Exception("Connection refused")
        
        hc = HealthChecker()
        result = hc.check_redis()
        
        assert result.name == "Redis"
        assert result.status == HealthStatus.UNHEALTHY
        assert "Connection refused" in result.message

    @patch("database.redis_conn.redis_conn", None)
    def test_check_redis_none(self):
        hc = HealthChecker()
        result = hc.check_redis()
        
        assert result.name == "Redis"
        assert result.status == HealthStatus.UNHEALTHY

    # キュー深度チェック
    @patch("services.health_checker.Queue")
    @patch("database.redis_conn.redis_conn")
    def test_check_queue_depth_healthy(self, mock_redis_conn, mock_queue_class):
        mock_queue = MagicMock()
        mock_queue.__len__ = MagicMock(return_value=5)
        mock_queue.started_job_registry.count = 2
        mock_queue.failed_job_registry.count = 1
        mock_queue_class.return_value = mock_queue
        
        hc = HealthChecker(queue_alert_threshold=100)
        result = hc.check_queue_depth()
        
        assert result.name == "QueueDepth"
        assert result.status == HealthStatus.HEALTHY
        assert "crawl_tasks" in result.details

    @patch("services.health_checker.Queue")
    @patch("database.redis_conn.redis_conn")
    def test_check_queue_depth_degraded(self, mock_redis_conn, mock_queue_class):
        mock_queue = MagicMock()
        mock_queue.__len__ = MagicMock(return_value=150)
        mock_queue.started_job_registry.count = 10
        mock_queue.failed_job_registry.count = 5
        mock_queue_class.return_value = mock_queue
        
        hc = HealthChecker(queue_alert_threshold=100)
        result = hc.check_queue_depth()
        
        assert result.name == "QueueDepth"
        assert result.status == HealthStatus.DEGRADED
        assert "exceeded threshold" in result.message

    @patch("services.health_checker.Queue")
    @patch("database.redis_conn.redis_conn")
    def test_check_queue_depth_failure(self, mock_redis_conn, mock_queue_class):
        mock_queue_class.side_effect = Exception("Redis error")
        
        hc = HealthChecker()
        result = hc.check_queue_depth()
        
        assert result.name == "QueueDepth"
        assert result.status == HealthStatus.UNHEALTHY

    # データベースチェック
    @patch("services.health_checker.get_session")
    def test_check_database_success(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.execute.return_value.first.return_value = (1,)
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        hc = HealthChecker()
        result = hc.check_database()
        
        assert result.name == "Database"
        assert result.status == HealthStatus.HEALTHY

    @patch("services.health_checker.get_session")
    def test_check_database_failure(self, mock_get_session):
        mock_get_session.side_effect = Exception("DB connection failed")
        
        hc = HealthChecker()
        result = hc.check_database()
        
        assert result.name == "Database"
        assert result.status == HealthStatus.UNHEALTHY

    # スケジューラチェック
    @patch("scheduler.scheduler_manager")
    def test_check_scheduler_healthy(self, mock_scheduler_manager):
        mock_scheduler_manager._is_running = True
        mock_scheduler_manager.list_jobs.return_value = [MagicMock(), MagicMock()]
        
        hc = HealthChecker()
        result = hc.check_scheduler()
        
        assert result.name == "Scheduler"
        assert result.status == HealthStatus.HEALTHY
        assert result.details["jobs_count"] == 2

    @patch("scheduler.scheduler_manager")
    def test_check_scheduler_not_running(self, mock_scheduler_manager):
        mock_scheduler_manager._is_running = False
        mock_scheduler_manager.list_jobs.return_value = []
        
        hc = HealthChecker()
        result = hc.check_scheduler()
        
        assert result.name == "Scheduler"
        assert result.status == HealthStatus.UNHEALTHY
        assert "not running" in result.message

    @patch("scheduler.scheduler_manager")
    def test_check_scheduler_error(self, mock_scheduler_manager):
        mock_scheduler_manager._is_running = True
        mock_scheduler_manager.list_jobs.side_effect = Exception("Scheduler error")
        
        hc = HealthChecker()
        result = hc.check_scheduler()
        
        assert result.name == "Scheduler"
        assert result.status == HealthStatus.DEGRADED

    # パイプライン最近実行チェック
    @patch("services.health_checker.get_session")
    def test_check_pipeline_recency_healthy(self, mock_get_session):
        mock_session = MagicMock()
        mock_metric = MagicMock()
        mock_metric.timestamp = datetime.utcnow() - timedelta(hours=1)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_metric
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        hc = HealthChecker()
        result = hc.check_pipeline_recency()
        
        assert result.name == "PipelineRecency"
        assert result.status == HealthStatus.HEALTHY
        assert result.details["recent_metric_found"] is True

    @patch("services.health_checker.get_session")
    def test_check_pipeline_recency_degraded(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        hc = HealthChecker()
        result = hc.check_pipeline_recency()
        
        assert result.name == "PipelineRecency"
        assert result.status == HealthStatus.DEGRADED
        assert "24 hours" in result.message

    @patch("services.health_checker.get_session")
    def test_check_pipeline_recency_error(self, mock_get_session):
        mock_get_session.side_effect = Exception("DB error")
        
        hc = HealthChecker()
        result = hc.check_pipeline_recency()
        
        assert result.name == "PipelineRecency"
        assert result.status == HealthStatus.DEGRADED

    # 落札データ品質チェック
    @patch("services.health_checker.get_quality_report")
    @patch("services.health_checker.get_session")
    def test_check_award_data_quality_healthy(self, mock_get_session, mock_get_quality_report):
        mock_get_quality_report.return_value = {
            "total_awards": 100,
            "missing_award_rate": 0,
            "missing_budget": 0,
            "missing_winner": 0,
            "duplicate_source_urls": 0,
        }
        
        hc = HealthChecker()
        result = hc.check_award_data_quality()
        
        assert result.name == "AwardDataQuality"
        assert result.status == HealthStatus.HEALTHY

    @patch("services.health_checker.get_quality_report")
    @patch("services.health_checker.get_session")
    def test_check_award_data_quality_degraded(self, mock_get_session, mock_get_quality_report):
        mock_get_quality_report.return_value = {
            "total_awards": 100,
            "missing_award_rate": 5,
            "missing_budget": 2,
            "missing_winner": 1,
            "duplicate_source_urls": 0,
        }
        
        hc = HealthChecker()
        result = hc.check_award_data_quality()
        
        assert result.name == "AwardDataQuality"
        assert result.status == HealthStatus.DEGRADED
        assert "issues found" in result.message

    @patch("services.health_checker.get_quality_report")
    @patch("services.health_checker.get_session")
    def test_check_award_data_quality_error(self, mock_get_session, mock_get_quality_report):
        mock_get_quality_report.side_effect = Exception("Quality check error")
        
        hc = HealthChecker()
        result = hc.check_award_data_quality()
        
        assert result.name == "AwardDataQuality"
        assert result.status == HealthStatus.UNHEALTHY

    # 資格システムチェック
    @patch("services.health_checker.get_session")
    def test_check_qualification_system_healthy(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.query.return_value.count.side_effect = [50, 100]
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        hc = HealthChecker()
        result = hc.check_qualification_system()
        
        assert result.name == "QualificationSystem"
        assert result.status == HealthStatus.HEALTHY
        assert result.details["qualification_tags"] == 50
        assert result.details["company_profiles"] == 100

    @patch("services.health_checker.get_session")
    def test_check_qualification_system_no_tags(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.query.return_value.count.side_effect = [0, 100]
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        hc = HealthChecker()
        result = hc.check_qualification_system()
        
        assert result.name == "QualificationSystem"
        assert result.status == HealthStatus.DEGRADED
        assert "empty" in result.message

    @patch("services.health_checker.get_session")
    def test_check_qualification_system_no_profiles(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.query.return_value.count.side_effect = [50, 0]
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        hc = HealthChecker()
        result = hc.check_qualification_system()
        
        assert result.name == "QualificationSystem"
        assert result.status == HealthStatus.DEGRADED
        assert "not registered" in result.message

    @patch("services.health_checker.get_session")
    def test_check_qualification_system_error(self, mock_get_session):
        mock_get_session.side_effect = Exception("DB error")
        
        hc = HealthChecker()
        result = hc.check_qualification_system()
        
        assert result.name == "QualificationSystem"
        assert result.status == HealthStatus.UNHEALTHY

    # 全体チェック
    @patch.object(HealthChecker, "check_redis")
    @patch.object(HealthChecker, "check_queue_depth")
    @patch.object(HealthChecker, "check_database")
    @patch.object(HealthChecker, "check_scheduler")
    @patch.object(HealthChecker, "check_pipeline_recency")
    @patch.object(HealthChecker, "check_award_data_quality")
    @patch.object(HealthChecker, "check_qualification_system")
    def test_check_all_healthy(self, mock_qual, mock_award, mock_pipeline, 
                                mock_sched, mock_db, mock_queue, mock_redis):
        # すべて HEALTHY
        for mock in [mock_redis, mock_queue, mock_db, mock_sched, mock_pipeline, mock_award, mock_qual]:
            mock.return_value = ComponentHealth("Test", HealthStatus.HEALTHY)
        
        hc = HealthChecker()
        result = hc.check_all()
        
        assert result["overall_status"] == "healthy"
        assert len(result["components"]) == 7

    @patch.object(HealthChecker, "check_redis")
    @patch.object(HealthChecker, "check_queue_depth")
    @patch.object(HealthChecker, "check_database")
    @patch.object(HealthChecker, "check_scheduler")
    @patch.object(HealthChecker, "check_pipeline_recency")
    @patch.object(HealthChecker, "check_award_data_quality")
    @patch.object(HealthChecker, "check_qualification_system")
    def test_check_all_unhealthy(self, mock_qual, mock_award, mock_pipeline,
                                  mock_sched, mock_db, mock_queue, mock_redis):
        # 1つ UNHEALTHY
        mock_redis.return_value = ComponentHealth("Redis", HealthStatus.UNHEALTHY)
        for mock in [mock_queue, mock_db, mock_sched, mock_pipeline, mock_award, mock_qual]:
            mock.return_value = ComponentHealth("Test", HealthStatus.HEALTHY)
        
        hc = HealthChecker()
        result = hc.check_all()
        
        assert result["overall_status"] == "unhealthy"

    @patch.object(HealthChecker, "check_redis")
    @patch.object(HealthChecker, "check_queue_depth")
    @patch.object(HealthChecker, "check_database")
    @patch.object(HealthChecker, "check_scheduler")
    @patch.object(HealthChecker, "check_pipeline_recency")
    @patch.object(HealthChecker, "check_award_data_quality")
    @patch.object(HealthChecker, "check_qualification_system")
    def test_check_all_degraded(self, mock_qual, mock_award, mock_pipeline,
                                 mock_sched, mock_db, mock_queue, mock_redis):
        # 1つ DEGRADED、UNHEALTHY なし
        mock_redis.return_value = ComponentHealth("Redis", HealthStatus.DEGRADED)
        for mock in [mock_queue, mock_db, mock_sched, mock_pipeline, mock_award, mock_qual]:
            mock.return_value = ComponentHealth("Test", HealthStatus.HEALTHY)
        
        hc = HealthChecker()
        result = hc.check_all()
        
        assert result["overall_status"] == "degraded"

    @patch.object(HealthChecker, "check_redis")
    @patch.object(HealthChecker, "check_queue_depth")
    @patch.object(HealthChecker, "check_database")
    @patch.object(HealthChecker, "check_scheduler")
    @patch.object(HealthChecker, "check_pipeline_recency")
    @patch.object(HealthChecker, "check_award_data_quality")
    @patch.object(HealthChecker, "check_qualification_system")
    def test_check_all_unhealthy_overrides_degraded(self, mock_qual, mock_award, mock_pipeline,
                                                     mock_sched, mock_db, mock_queue, mock_redis):
        # UNHEALTHY と DEGRADED が混在 -> UNHEALTHY 優先
        mock_redis.return_value = ComponentHealth("Redis", HealthStatus.UNHEALTHY)
        mock_queue.return_value = ComponentHealth("QueueDepth", HealthStatus.DEGRADED)
        for mock in [mock_db, mock_sched, mock_pipeline, mock_award, mock_qual]:
            mock.return_value = ComponentHealth("Test", HealthStatus.HEALTHY)
        
        hc = HealthChecker()
        result = hc.check_all()
        
        assert result["overall_status"] == "unhealthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])