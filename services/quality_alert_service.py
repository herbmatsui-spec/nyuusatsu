"""品質アラート評価サービス

- `evaluate(metric_name, value)` がしきい値を比較し、'warn', 'alert', 'ok' を返す
- `send_alert(metric_name, value, level)` が `notifier.notify_quality_issue` を呼び出す
"""

from database.models.quality_threshold import QualityThreshold
from notifier import notify_quality_issue

class QualityAlertService:
    def __init__(self, session):
        self.session = session

    def evaluate(self, metric_name: str, value: float) -> str:
        """しきい値を取得し、レベルを判定。存在しない場合は 'ok' を返す。"""
        threshold = self.session.query(QualityThreshold).filter_by(metric_name=metric_name).first()
        if not threshold:
            return "ok"
        if value >= threshold.alert_at:
            return "alert"
        if value >= threshold.warn_at:
            return "warn"
        return "ok"

    def send_alert(self, metric_name: str, value: float, level: str) -> bool:
        """レベルに応じて通知を送信。 level は 'warn' または 'alert'。"""
        if level not in ("warn", "alert"):
            return False
        return notify_quality_issue(metric_name, value, level)
