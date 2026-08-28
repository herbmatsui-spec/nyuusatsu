from datetime import datetime, timedelta
from typing import List
from database.session import get_db
from database.models.pipeline_metric import PipelineMetric

def generate_prometheus_metrics(hours: int = 24) -> str:
    """
    SQLiteに保存されているメトリクス情報から、
    Prometheus標準フォーマットのメトリクス文字列を生成して返す。
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    lines = []
    
    with get_db() as session:
        # 1. 各ステージの処理成功件数と失敗件数 (success = 1.0 または 0.0)
        # pipeline_stage_success_total Counter
        metrics = session.query(PipelineMetric).filter(
            PipelineMetric.timestamp >= cutoff,
            PipelineMetric.metric_name == "success"
        ).all()
        
        # クラスター内集計
        success_counts = {}
        for m in metrics:
            key = (m.stage, m.metric_value == 1.0)
            success_counts[key] = success_counts.get(key, 0) + 1
            
        lines.append("# HELP pipeline_stage_success_total Total successful/failed runs in pipeline stages.")
        lines.append("# TYPE pipeline_stage_success_total counter")
        for (stage, is_success), count in success_counts.items():
            status_str = "success" if is_success else "failed"
            lines.append(f'pipeline_stage_success_total{{stage="{stage}",status="{status_str}"}} {count}')

        # 2. 平均処理時間
        # pipeline_stage_duration_milliseconds Gauge
        durations = session.query(PipelineMetric).filter(
            PipelineMetric.timestamp >= cutoff,
            PipelineMetric.metric_name == "duration_ms"
        ).all()
        
        duration_sums = {}
        duration_counts = {}
        for m in durations:
            duration_sums[m.stage] = duration_sums.get(m.stage, 0.0) + m.metric_value
            duration_counts[m.stage] = duration_counts.get(m.stage, 0) + 1
            
        lines.append("\n# HELP pipeline_stage_duration_avg_milliseconds Average duration of pipeline stages in milliseconds.")
        lines.append("# TYPE pipeline_stage_duration_avg_milliseconds gauge")
        for stage, total in duration_sums.items():
            count = duration_counts[stage]
            avg = total / count if count > 0 else 0.0
            lines.append(f'pipeline_stage_duration_avg_milliseconds{{stage="{stage}"}} {avg:.2f}')

    return "\n".join(lines) + "\n"
