import pytest
from database.session import get_db
from database.models.alert_history import AlertHistory
from services.health_checker import HealthChecker, HealthStatus
from services.alert_manager import AlertManager

def test_health_checker_database():
    checker = HealthChecker()
    db_health = checker.check_database()
    assert db_health.name == "Database"
    assert db_health.status == HealthStatus.HEALTHY

def test_health_checker_check_all():
    checker = HealthChecker()
    res = checker.check_all()
    
    assert "overall_status" in res
    assert "timestamp" in res
    assert "components" in res
    assert "Database" in res["components"]

def test_alert_manager_evaluation():
    # 連続失敗閾値 2回 のマネージャをテスト用に生成
    alert_manager = AlertManager(failure_threshold=2)
    AlertManager._consecutive_failures.clear()
    
    component = "TestComponent"
    
    # 1回目の失敗
    alert_manager.evaluate_and_alert(component, is_healthy=False, error_message="First failure")
    assert AlertManager.get_failures().get(component) == 1
    
    # アラート履歴にまだ登録されていないことを確認 (閾値は2なので)
    with get_db() as session:
        alert = session.query(AlertHistory).filter(
            AlertHistory.component == component
        ).first()
        assert alert is None
        
    # 2回目の失敗 (閾値到達 -> アラート発報 & 履歴記録)
    alert_manager.evaluate_and_alert(component, is_healthy=False, error_message="Second failure")
    assert AlertManager.get_failures().get(component) == 2
    
    with get_db() as session:
        alert = session.query(AlertHistory).filter(
            AlertHistory.component == component,
            AlertHistory.resolved_at.is_(None)
        ).first()
        assert alert is not None
        assert alert.severity == "CRITICAL"
        assert alert.message == "Second failure"
        
    # 3回目 (復旧 -> リカバリ通知 & 履歴のresolved_at更新)
    alert_manager.evaluate_and_alert(component, is_healthy=True)
    assert AlertManager.get_failures().get(component) == 0
    
    with get_db() as session:
        alert = session.query(AlertHistory).filter(
            AlertHistory.component == component
        ).first()
        assert alert is not None
        assert alert.resolved_at is not None  # 復旧日時が記録されていること
