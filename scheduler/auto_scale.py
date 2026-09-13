"""自動スケーリング - キューサイズ・CPU使用率に基づくジョブ数調整 (Step 46)。"""

import os
import time
import logging
import threading
from datetime import datetime
from typing import Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 環境変数設定
AUTO_SCALE_ENABLED = os.getenv("SCHEDULER_AUTO_SCALE", "false").lower() == "true"
CHECK_INTERVAL = int(os.getenv("SCHEDULER_SCALE_CHECK_INTERVAL", "60"))  # 秒
QUEUE_HIGH_THRESHOLD = int(os.getenv("SCHEDULER_QUEUE_HIGH", "100"))
QUEUE_LOW_THRESHOLD = int(os.getenv("SCHEDULER_QUEUE_LOW", "10"))
CPU_HIGH_THRESHOLD = float(os.getenv("SCHEDULER_CPU_HIGH", "80.0"))
CPU_LOW_THRESHOLD = float(os.getenv("SCHEDULER_CPU_LOW", "30.0"))
MIN_WORKERS = int(os.getenv("SCHEDULER_MIN_WORKERS", "1"))
MAX_WORKERS = int(os.getenv("SCHEDULER_MAX_WORKERS", "10"))
SCALE_UP_COOLDOWN = int(os.getenv("SCHEDULER_SCALE_UP_COOLDOWN", "300"))  # 5分
SCALE_DOWN_COOLDOWN = int(os.getenv("SCHEDULER_SCALE_DOWN_COOLDOWN", "600"))  # 10分


@dataclass
class ScalingMetrics:
    """スケーリング判定用メトリクス。"""
    queue_depth: int = 0
    cpu_usage: float = 0.0
    active_workers: int = 0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AutoScaler:
    """APSchedulerのワーカー数を動的に調整する自動スケーラー。"""
    
    def __init__(
        self,
        scheduler_get_jobs: Callable,
        executor_set_max_workers: Callable[[int], None],
        get_queue_depth: Optional[Callable[[], int]] = None,
        get_cpu_usage: Optional[Callable[[], float]] = None,
    ):
        """
        Args:
            scheduler_get_jobs: スケジューラからジョブ一覧を取得する関数
            executor_set_max_workers: エグゼキュータのmax_workersを設定する関数
            get_queue_depth: キュー深度を取得する関数（省略可）
            get_cpu_usage: CPU使用率を取得する関数（省略可）
        """
        self.scheduler_get_jobs = scheduler_get_jobs
        self.executor_set_max_workers = executor_set_max_workers
        self.get_queue_depth = get_queue_depth or self._default_queue_depth
        self.get_cpu_usage = get_cpu_usage or self._default_cpu_usage
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_scale_up = 0
        self._last_scale_down = 0
        self._current_workers = MIN_WORKERS
        
    def _default_queue_depth(self) -> int:
        """デフォルトのキュー深度取得（APSchedulerジョブ数）。"""
        try:
            jobs = self.scheduler_get_jobs()
            return len([j for j in jobs if j.next_run_time is not None])
        except Exception:
            return 0
    
    def _default_cpu_usage(self) -> float:
        """デフォルトのCPU使用率取得。"""
        try:
            import psutil
            return psutil.cpu_percent(interval=1)
        except Exception:
            return 0.0
    
    def start(self) -> None:
        """自動スケーリングを開始。"""
        if not AUTO_SCALE_ENABLED:
            logger.info("Auto-scaling disabled (set SCHEDULER_AUTO_SCALE=true to enable)")
            return
        
        if self._running:
            logger.warning("Auto-scaler already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"Auto-scaler started (check interval: {CHECK_INTERVAL}s)")
    
    def stop(self) -> None:
        """自動スケーリングを停止。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Auto-scaler stopped")
    
    def _run_loop(self) -> None:
        """メインループ: 定期的にメトリクス収集・スケーリング判定。"""
        while self._running:
            try:
                self._evaluate_and_scale()
            except Exception as e:
                logger.error(f"Auto-scaler evaluation error: {e}", exc_info=True)
            
            time.sleep(CHECK_INTERVAL)
    
    def _evaluate_and_scale(self) -> None:
        """メトリクス収集し、スケーリング判定・実行。"""
        now = time.time()
        
        # メトリクス収集
        metrics = ScalingMetrics(
            queue_depth=self.get_queue_depth(),
            cpu_usage=self.get_cpu_usage(),
            active_workers=self._current_workers,
        )
        
        # スケールアップ判定
        should_scale_up = (
            metrics.queue_depth > QUEUE_HIGH_THRESHOLD or
            metrics.cpu_usage > CPU_HIGH_THRESHOLD
        )
        
        # スケールダウン判定
        should_scale_down = (
            metrics.queue_depth < QUEUE_LOW_THRESHOLD and
            metrics.cpu_usage < CPU_LOW_THRESHOLD
        )
        
        # クールダウンチェック
        can_scale_up = (now - self._last_scale_up) > SCALE_UP_COOLDOWN
        can_scale_down = (now - self._last_scale_down) > SCALE_DOWN_COOLDOWN
        
        # スケーリング実行
        if should_scale_up and can_scale_up:
            target = min(self._current_workers + 1, MAX_WORKERS)
            if target > self._current_workers:
                self._scale_to(target)
                self._last_scale_up = now
                logger.info(f"Scaled UP: {self._current_workers} -> {target} workers "
                           f"(queue={metrics.queue_depth}, cpu={metrics.cpu_usage:.1f}%)")
        
        elif should_scale_down and can_scale_down:
            target = max(self._current_workers - 1, MIN_WORKERS)
            if target < self._current_workers:
                self._scale_to(target)
                self._last_scale_down = now
                logger.info(f"Scaled DOWN: {self._current_workers} -> {target} workers "
                           f"(queue={metrics.queue_depth}, cpu={metrics.cpu_usage:.1f}%)")
    
    def _scale_to(self, target_workers: int) -> None:
        """ワーカー数を設定。"""
        try:
            self.executor_set_max_workers(target_workers)
            self._current_workers = target_workers
        except Exception as e:
            logger.error(f"Failed to set max_workers to {target_workers}: {e}")


# グローバルインスタンス
_auto_scaler: Optional[AutoScaler] = None


def init_auto_scaler(
    scheduler_get_jobs: Callable,
    executor_set_max_workers: Callable[[int], None],
    get_queue_depth: Optional[Callable[[], int]] = None,
    get_cpu_usage: Optional[Callable[[], float]] = None,
) -> AutoScaler:
    """自動スケーラーを初期化・開始。"""
    global _auto_scaler
    _auto_scaler = AutoScaler(
        scheduler_get_jobs=scheduler_get_jobs,
        executor_set_max_workers=executor_set_max_workers,
        get_queue_depth=get_queue_depth,
        get_cpu_usage=get_cpu_usage,
    )
    _auto_scaler.start()
    return _auto_scaler


def get_auto_scaler() -> Optional[AutoScaler]:
    """初期化済みの自動スケーラーを取得。"""
    return _auto_scaler


def shutdown_auto_scaler() -> None:
    """自動スケーラーを停止。"""
    global _auto_scaler
    if _auto_scaler:
        _auto_scaler.stop()
        _auto_scaler = None