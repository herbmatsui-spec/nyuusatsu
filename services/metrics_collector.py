import json
import time
import logging
import threading
from datetime import datetime
from contextlib import contextmanager
from database.session import get_db
from database.models.pipeline_metric import PipelineMetric

logger = logging.getLogger("MetricsCollector")

class MetricsCollector:
    """
    アプリケーションのパフォーマンスメトリクスを収集するためのベースクラス。
    """
    @staticmethod
    def record(stage: str, metric_name: str, value: float, labels: dict = None, trace_id: str = ""):
        """単一のメトリクスを同期的に即時データベースに保存する"""
        try:
            with get_db() as session:
                metric = PipelineMetric(
                    stage=stage,
                    metric_name=metric_name,
                    metric_value=value,
                    labels=json.dumps(labels or {}, ensure_ascii=False),
                    trace_id=trace_id
                )
                session.add(metric)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to record metric: {e}", exc_info=True)

    @classmethod
    @contextmanager
    def measure(cls, stage: str, metric_name: str = "duration_ms", labels: dict = None, trace_id: str = ""):
        """処理時間をミリ秒単位で計測し、メトリクスとして自動登録するコンテキストマネージャ"""
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed = (time.monotonic() - start) * 1000
            cls.record(stage, metric_name, elapsed, labels, trace_id)


class BufferedMetricsCollector:
    """
    メモリバッファを使用し、高頻度なメトリクス書き込みによるDB負荷を軽減する
    スレッドセーフなコレクター。
    """
    _buffer = []
    _buffer_size = 30  # バッファサイズ閾値
    _lock = threading.Lock()

    @classmethod
    def record(cls, stage: str, metric_name: str, value: float, labels: dict = None, trace_id: str = ""):
        """メトリクスを一時的にバッファに格納し、閾値を超えたら一括保存する"""
        with cls._lock:
            cls._buffer.append({
                "stage": stage,
                "metric_name": metric_name,
                "metric_value": value,
                "labels": json.dumps(labels or {}, ensure_ascii=False),
                "trace_id": trace_id,
                "timestamp": datetime.utcnow()
            })
            
            if len(cls._buffer) >= cls._buffer_size:
                cls.flush()

    @classmethod
    def flush(cls):
        """バッファにあるすべてのメトリクスを一括でDBに書き込む"""
        if not cls._buffer:
            return
        
        to_save = list(cls._buffer)
        cls._buffer.clear()
        
        try:
            with get_db() as session:
                for item in to_save:
                    metric = PipelineMetric(
                        stage=item["stage"],
                        metric_name=item["metric_name"],
                        metric_value=item["metric_value"],
                        labels=item["labels"],
                        trace_id=item["trace_id"],
                        timestamp=item["timestamp"]
                    )
                    session.add(metric)
                session.commit()
                logger.debug(f"Successfully flushed {len(to_save)} metrics to DB.")
        except Exception as e:
            logger.error(f"Failed to flush buffered metrics: {e}", exc_info=True)
            # 失敗時はバッファに戻すなどの回復処理も検討可能だが、ここでは再発防止とログ出力に留める

    @classmethod
    @contextmanager
    def measure(cls, stage: str, metric_name: str = "duration_ms", labels: dict = None, trace_id: str = ""):
        """バッファリング版の処理時間計測コンテキストマネージャ"""
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed = (time.monotonic() - start) * 1000
            cls.record(stage, metric_name, elapsed, labels, trace_id)
