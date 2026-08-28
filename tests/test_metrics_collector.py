import time
from datetime import datetime, timedelta
from database.session import get_db
from database.models.pipeline_metric import PipelineMetric
from services.metrics_collector import MetricsCollector, BufferedMetricsCollector
from scripts.cleanup_metrics import cleanup_old_metrics

def test_metrics_collector_record():
    stage = "test_stage"
    metric_name = "test_metric"
    value = 100.5
    labels = {"job_id": 999}
    trace_id = "test_trace_123"
    
    # 即時保存のテスト
    MetricsCollector.record(stage, metric_name, value, labels, trace_id)
    
    with get_db() as session:
        metric = session.query(PipelineMetric).filter(
            PipelineMetric.trace_id == trace_id
        ).first()
        
        assert metric is not None
        assert metric.stage == stage
        assert metric.metric_name == metric_name
        assert metric.metric_value == value
        assert "999" in metric.labels

def test_metrics_collector_measure():
    trace_id = "measure_trace"
    
    with MetricsCollector.measure("test_measure", "duration", trace_id=trace_id):
        time.sleep(0.05)
        
    with get_db() as session:
        metric = session.query(PipelineMetric).filter(
            PipelineMetric.trace_id == trace_id
        ).first()
        
        assert metric is not None
        assert metric.metric_value >= 50.0  # ミリ秒単位なので50ms以上になっているはず

def test_buffered_metrics_collector():
    BufferedMetricsCollector._buffer.clear()
    
    # 閾値が30なので、29件まではDB保存されずバッファにとどまる
    for i in range(29):
        BufferedMetricsCollector.record("buf_stage", "count", 1.0, trace_id=f"trace_{i}")
        
    with get_db() as session:
        metric = session.query(PipelineMetric).filter(
            PipelineMetric.stage == "buf_stage"
        ).first()
        assert metric is None  # まだ書き込まれていない
        
    # 30件目で自動フラッシュされる
    BufferedMetricsCollector.record("buf_stage", "count", 1.0, trace_id="trace_30")
    
    with get_db() as session:
        metrics = session.query(PipelineMetric).filter(
            PipelineMetric.stage == "buf_stage"
        ).all()
        assert len(metrics) == 30

def test_cleanup_metrics():
    # 古いレコードをテスト用に作成
    with get_db() as session:
        # 31日前のダミーメトリクス
        old_metric = PipelineMetric(
            timestamp=datetime.utcnow() - timedelta(days=31),
            stage="old_stage",
            metric_name="old_metric",
            metric_value=1.0,
            trace_id="old_trace"
        )
        session.add(old_metric)
        session.commit()
        
    # クリーンアップ実行 (30日保持ルール)
    cleanup_old_metrics(30)
    
    with get_db() as session:
        metric = session.query(PipelineMetric).filter(
            PipelineMetric.trace_id == "old_trace"
        ).first()
        assert metric is None  # 正常に削除されたこと
