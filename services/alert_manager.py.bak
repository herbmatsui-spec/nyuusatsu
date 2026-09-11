import logging
from datetime import datetime
from database.session import get_db
from database.models.crawl import SystemSetting
from services.notification_service import NotificationService
from services.crawl_service import CrawlService

logger = logging.getLogger("AlertManager")

class AlertManager:
    """
    ヘルスチェックの結果を評価し、エラー状態が指定回数（デフォルト3回）連続した場合に
    Slack / LINE 通知を送信するアラートマネージャー。
    """
    _consecutive_failures = {}

    def __init__(self, failure_threshold: int = 3):
        self.failure_threshold = failure_threshold
        # NotificationServiceの初期化にCrawlServiceが必要
        with get_db() as session:
            crawl_service = CrawlService(session)
            self.notifier = NotificationService(crawl_service)

    def evaluate_and_alert(self, component: str, is_healthy: bool, error_message: str = ""):
        """
        特定のコンポーネントの状態を評価し、連続で失敗している場合にアラートを発報する。
        """
        if not is_healthy:
            # 失敗カウントを増やす
            current_failures = self._consecutive_failures.get(component, 0) + 1
            self._consecutive_failures[component] = current_failures
            
            logger.warning(f"Component {component} is unhealthy ({current_failures}/{self.failure_threshold}): {error_message}")
            
            # 閾値に達した段階でアラート送信（それ以降は連続アラートノイズを防ぐため、特定のタイミングでのみ送る）
            if current_failures == self.failure_threshold:
                self._send_alert(component, error_message, severity="CRITICAL")
            elif current_failures > self.failure_threshold and current_failures % 30 == 0:
                # 長時間復旧しない場合のリマインダー (30分間隔など)
                self._send_alert(component, f"[Reminder] {error_message}", severity="CRITICAL")
        else:
            # 復旧した場合
            previous_failures = self._consecutive_failures.get(component, 0)
            self._consecutive_failures[component] = 0
            
            if previous_failures >= self.failure_threshold:
                # アラートが飛んでいたものが復旧したため、リカバリ通知を送る
                self._send_alert(component, "Component recovered to healthy status.", severity="INFO", is_recovery=True)

    def _send_alert(self, component: str, message: str, severity: str = "CRITICAL", is_recovery: bool = False):
        emoji = "✅" if is_recovery else "🚨"
        title = "【復旧】" if is_recovery else "【システム警告】"
        
        full_message = (
            f"{emoji} {title} {component} 監視アラート\n"
            f"■ 発生時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"■ レベル: {severity}\n"
            f"■ 詳細: {message}\n"
        )
        
        logger.info(f"Sending alert notification for {component} (recovery={is_recovery})")
        
        # Slack / LINEへの通知
        try:
            self.notifier.send_slack_notification(full_message)
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            
        try:
            self.notifier.send_line_notification(full_message)
        except Exception as e:
            logger.error(f"Failed to send LINE alert: {e}")

        # アラート履歴の保存
        try:
            self._save_to_history(component, severity, message, is_recovery)
        except Exception as e:
            logger.error(f"Failed to save alert history: {e}")

    def _save_to_history(self, component: str, severity: str, message: str, is_recovery: bool):
        from database.models.alert_history import AlertHistory
        with get_db() as session:
            if is_recovery:
                # 過去の未復旧アラートを探して solved_at を埋める
                unresolved = session.query(AlertHistory).filter(
                    AlertHistory.component == component,
                    AlertHistory.resolved_at.is_(None)
                ).all()
                for alert in unresolved:
                    alert.resolved_at = datetime.utcnow()
            else:
                alert = AlertHistory(
                    component=component,
                    severity=severity,
                    message=message
                )
                session.add(alert)
            session.commit()
            
    @classmethod
    def get_failures(cls):
        return cls._consecutive_failures
