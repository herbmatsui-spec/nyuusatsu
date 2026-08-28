"""品質メトリクス収集ジョブ

- 定期的に呼び出され、QualityMetricsService が計算したメトリクスをデータベースに保存します。
- スケジューラ (cron / APScheduler) から実行することを想定しています。
"""

from database.engine import get_session
from services.quality_metrics_service import QualityMetricsService
from database.models.quality_metric import QualityMetric

def run():
    with get_session() as session:
        qms = QualityMetricsService(session)
        # 欠落フィールドメトリクス
        missing = qms.count_missing_fields()
        for field, cnt in missing.items():
            metric = QualityMetric(metric_name=f"missing_{field}", value=cnt)
            session.add(metric)
        # 重複件数
        dup_cnt = qms.count_duplicates()
        session.add(QualityMetric(metric_name="duplicate_count", value=dup_cnt))
        # カバレッジ率
        cov = qms.coverage_rate()
        session.add(QualityMetric(metric_name="coverage_rate", value=cov))
        # 日々の変化量（過去 1 日）
        delta = qms.daily_delta(days=1)
        session.add(QualityMetric(metric_name="daily_new", value=delta.get("new", 0)))
        session.add(QualityMetric(metric_name="daily_updated", value=delta.get("updated", 0)))
        session.commit()
        print("品質メトリクスを収集・保存しました")

if __name__ == "__main__":
    run()
