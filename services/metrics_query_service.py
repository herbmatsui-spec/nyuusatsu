import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import func
from database.session import get_db
from database.models.pipeline_metric import PipelineMetric

class MetricsQueryService:
    """
    ダッシュボードやAPI用データソースとして、
    SQLite内のパイプラインメトリクスをクエリ・集計するサービス。
    """
    def get_pipeline_summary(self, hours: int = 24) -> Dict[str, Any]:
        """直近N時間におけるパイプライン各ステージの主要統計のサマリーを取得する"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        summary = {}
        
        with get_db() as session:
            # 1. 各ステージの総処理試行回数 (success = 1.0 または 0.0)
            status_metrics = session.query(
                PipelineMetric.stage,
                PipelineMetric.metric_value,
                func.count(PipelineMetric.id).label("count")
            ).filter(
                PipelineMetric.timestamp >= cutoff,
                PipelineMetric.metric_name == "success"
            ).group_by(
                PipelineMetric.stage,
                PipelineMetric.metric_value
            ).all()

            for stage in ["crawl", "download", "analysis", "task_queue"]:
                summary[stage] = {"success": 0, "failed": 0, "total": 0, "duration_avg_ms": 0.0}

            for row in status_metrics:
                stage = row.stage
                is_success = row.metric_value == 1.0
                count = row.count
                
                if stage in summary:
                    if is_success:
                        summary[stage]["success"] += count
                    else:
                        summary[stage]["failed"] += count
                    summary[stage]["total"] += count

            # 2. 平均処理時間の集計
            duration_metrics = session.query(
                PipelineMetric.stage,
                func.avg(PipelineMetric.metric_value).label("avg_duration")
            ).filter(
                PipelineMetric.timestamp >= cutoff,
                PipelineMetric.metric_name == "duration_ms"
            ).group_by(
                PipelineMetric.stage
            ).all()

            for row in duration_metrics:
                if row.stage in summary:
                    summary[row.stage]["duration_avg_ms"] = round(row.avg_duration or 0.0, 2)

            return summary

    def get_stage_timeseries(self, stage: str, metric_name: str = "success", hours: int = 24) -> List[Dict[str, Any]]:
        """特定のステージ・メトリクスの時間単位推移（時系列データ）を取得する"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        with get_db() as session:
            # 1時間ごとにグルーピングして集計
            # SQLite の strftime を使用
            results = session.query(
                func.strftime("%Y-%m-%d %H:00:00", PipelineMetric.timestamp).label("hour"),
                func.count(PipelineMetric.id).label("count"),
                func.avg(PipelineMetric.metric_value).label("avg_value")
            ).filter(
                PipelineMetric.timestamp >= cutoff,
                PipelineMetric.stage == stage,
                PipelineMetric.metric_name == metric_name
            ).group_by(
                "hour"
            ).order_by(
                "hour"
            ).all()

            return [
                {
                    "time": row.hour,
                    "count": row.count,
                    "value": round(row.avg_value or 0.0, 2)
                }
                for row in results
            ]

    def get_error_distribution(self, hours: int = 24) -> List[Dict[str, Any]]:
        """直近N時間で発生したエラー（成否=0のレコード）の内訳をステージ別・エラー種別ごとに取得する"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        with get_db() as session:
            failed_records = session.query(
                PipelineMetric.stage,
                PipelineMetric.labels
            ).filter(
                PipelineMetric.timestamp >= cutoff,
                PipelineMetric.metric_name == "success",
                PipelineMetric.metric_value == 0.0
            ).all()

            error_counts = {}
            for row in failed_records:
                stage = row.stage
                try:
                    labels = json.loads(row.labels) if row.labels else {}
                    error_type = labels.get("error", "UnknownError")
                except:
                    error_type = "UnknownError"
                
                key = (stage, error_type)
                error_counts[key] = error_counts.get(key, 0) + 1

            return [
                {
                    "stage": k[0],
                    "error_type": k[1],
                    "count": count
                }
                for k, count in error_counts.items()
            ]
