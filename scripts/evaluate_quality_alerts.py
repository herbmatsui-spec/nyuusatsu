"""品質アラート評価ジョブ

- DB に保存された最新の品質メトリクスを取得し、設定されたしきい値と比較
- しきい値を超えた場合は QualityAlertService.send_alert を呼び出す
  (Slack + LINE 通知、Redis 重複抑制、QualityAlert DB 保存を含む)
- 定期実行 (cron / APScheduler) 用スクリプト
"""

import logging

from sqlalchemy import func

from database.engine import get_session, engine
from database.models import create_all_quality_tables
from services.quality_alert_service import QualityAlertService
from database.models.quality_metric import QualityMetric

logger = logging.getLogger(__name__)


def run():
    create_all_quality_tables(engine)

    with get_session() as session:
        alert_service = QualityAlertService(session)
        sub = session.query(
            QualityMetric.metric_name,
            func.max(QualityMetric.recorded_at).label("max_at")
        ).group_by(QualityMetric.metric_name).subquery()
        latest_metrics = session.query(QualityMetric).join(
            sub,
            (QualityMetric.metric_name == sub.c.metric_name) & (QualityMetric.recorded_at == sub.c.max_at)
        ).all()

        alert_count = 0
        for metric in latest_metrics:
            level = alert_service.evaluate(metric.metric_name, metric.value)
            if level in ("warn", "alert"):
                if alert_service.send_alert(metric.metric_name, metric.value, level):
                    alert_count += 1
                else:
                    logger.info(
                        "Alert not sent for %s (dedup or notification failure): level=%s value=%s",
                        metric.metric_name, level, metric.value,
                    )

        logger.info("評価完了: %d 件のメトリクスを処理、%d 件のアラートを送信", len(latest_metrics), alert_count)
        print(f"評価完了: {len(latest_metrics)} 件のメトリクスを処理、{alert_count} 件のアラートを送信")


if __name__ == "__main__":
    run()
