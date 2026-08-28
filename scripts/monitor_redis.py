import logging
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.health_checker import HealthChecker, HealthStatus
from utils.logger import setup_logging

setup_logging("redis_monitor")
logger = logging.getLogger("redis_monitor")

def main():
    checker = HealthChecker()
    result = checker.check_redis()
    
    logger.info(f"Redis Health Status: {result.status.value}")
    if result.status != HealthStatus.HEALTHY:
        logger.error(f"Redis check failed: {result.message}")
        
        # Slack/LINE通知はAlertManagerが評価する仕組みに移行したため、
        # ここでは評価＆アラート発報をAlertManagerに委譲する。
        from services.alert_manager import AlertManager
        alert_manager = AlertManager()
        alert_manager.evaluate_and_alert("Redis", is_healthy=False, error_message=result.message)
        sys.exit(1)
        
    logger.info("Redis is running normally.")
    sys.exit(0)

if __name__ == "__main__":
    main()
