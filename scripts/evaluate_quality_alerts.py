"""品質アラート評価ジョブ

- DB に保存された最新の品質メトリクスを取得し、設定されたしきい値と比較
- しきい値を超えた場合は notifier.notify_quality_issue を呼び出す
- 定期実行 (cron / APScheduler) 用スクリプト
"""

from database.engine import get_session
from services.quality_alert_service import QualityAlertService
from database.models.quality_metric import QualityMetric
from sqlalchemy import func

def run():
    with get_session() as session:
        alert_service = QualityAlertService(session)
        # 最新のメトリクス取得（metric_name ごとに最大 recorded_at）
        sub = session.query(
            QualityMetric.metric_name,
            func.max(QualityMetric.recorded_at).label("max_at")
        ).group_by(QualityMetric.metric_name).subquery()
        latest_metrics = session.query(QualityMetric).join(
            sub,
            (QualityMetric.metric_name == sub.c.metric_name) & (QualityMetric.recorded_at == sub.c.max_at)
        ).all()
        for metric in latest_metrics:
            level = alert_service.evaluate(metric.metric_name, metric.value)
            if level in ("warn", "alert"):
                alert_service.send_alert(metric.metric_name, metric.value, level)
        print(f"評価完了: {len(latest_metrics)} 件のメトリクスを処理")

if __name__ == "__main__":
    run()
