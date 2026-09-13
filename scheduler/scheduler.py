import os
import logging
import time
import random
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from crawler_task import execute_crawl
from services.url_monitor_task import run_url_monitor
from services.award_crawl_task import run_award_crawl
from scheduler_jobs.forecast_crawl_job import crawl_all_forecasts
from database.engine import DATABASE_URL
from utils.notifier import Notifier
from database.session import get_db
from database.models.crawl_config import CrawlConfig
from crawler.pipeline import trigger_agency_crawl

# --- Step 39: Structured JSON logging ---
class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, "job_id"):
            log_entry["job_id"] = record.job_id
        if hasattr(record, "duration"):
            log_entry["duration_seconds"] = record.duration
        if hasattr(record, "status"):
            log_entry["status"] = record.status
        if hasattr(record, "error"):
            log_entry["error"] = record.error
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


def setup_json_logging():
    """Configure JSON structured logging for scheduler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)
    
    # Also configure apscheduler loggers
    for name in ["apscheduler", "apscheduler.scheduler", "apscheduler.executors.default"]:
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

logger = logging.getLogger(__name__)

jobstores = {
    'default': SQLAlchemyJobStore(url=DATABASE_URL)
}

notifier = Notifier()

# --- Step 33: Exception classification for scheduler jobs ---

class TransientError(Exception):
    """Recoverable error: should retry with backoff."""
    pass


class FatalError(Exception):
    """Unrecoverable error: log and move on, do not retry."""
    pass


class ConfigurationError(Exception):
    """Misconfiguration: alert immediately, fix required."""
    pass


# --- Step 36: Dead Letter Queue ---

_DEAD_LETTER_QUEUE_PATH = Path(os.getenv("SCHEDULER_DLQ_PATH", "data/scheduler_dlq.json"))


def _enqueue_dlq(job_id: str, error: str, payload: dict | None = None) -> None:
    """Append a failed job to the Dead Letter Queue file."""
    entry = {
        "job_id": job_id,
        "error": error,
        "payload": payload or {},
        "failed_at": datetime.utcnow().isoformat(),
    }
    _DEAD_LETTER_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        entries: list = []
        if _DEAD_LETTER_QUEUE_PATH.exists():
            with open(_DEAD_LETTER_QUEUE_PATH, "r") as f:
                try:
                    entries = json.load(f)
                except json.JSONDecodeError:
                    entries = []
        entries.append(entry)
        with open(_DEAD_LETTER_QUEUE_PATH, "w") as f:
            json.dump(entries, f, indent=2)
        logger.warning(f"Job {job_id} moved to DLQ: {error}")
    except Exception as e:
        logger.error(f"Failed to write to DLQ for job {job_id}: {e}", exc_info=True)


# --- Step 34/35: Retry with exponential backoff and max retries ---

_SCHEDULER_MAX_RETRIES = int(os.getenv("SCHEDULER_MAX_RETRIES", "3"))
_SCHEDULER_BASE_RETRY_DELAY = float(os.getenv("SCHEDULER_BASE_RETRY_DELAY", "2.0"))

# In-memory retry tracker: { job_id: retry_count }
_retry_counts: dict = {}


def _get_retry_count(job_id: str) -> int:
    return _retry_counts.get(job_id, 0)


def _increment_retry(job_id: str) -> int:
    _retry_counts[job_id] = _retry_counts.get(job_id, 0) + 1
    return _retry_counts[job_id]


def _reset_retry(job_id: str) -> None:
    _retry_counts.pop(job_id, None)


def _compute_backoff(attempt: int) -> float:
    """Exponential backoff with jitter: base * 2^attempt + random(0, 0.5)."""
    return _SCHEDULER_BASE_RETRY_DELAY * (2 ** min(attempt, 5)) + random.uniform(0, 0.5)


# --- Step 40: Scheduler metrics ---

def _record_job_metric(job_id: str, status: str, duration: float) -> None:
    """Record scheduler job execution metrics to DB quality_metric table."""
    try:
        from database.models.quality_metric import QualityMetric
        with get_db() as session:
            metric = QualityMetric(
                metric_name=f"scheduler_job_{job_id}",
                value=duration,
                recorded_at=datetime.utcnow(),
                period_start=datetime.utcnow() - timedelta(seconds=duration),
                period_end=datetime.utcnow(),
            )
            session.add(metric)
            session.commit()
    except Exception as e:
        logger.debug(f"Failed to record scheduler metric for {job_id}: {e}")


class SchedulerManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler(jobstores=jobstores)
        self._is_running = False
        self.logger = logging.getLogger(__name__)
        self._max_retries: int = _SCHEDULER_MAX_RETRIES

    def _safe_run_job(self, job_id: str, func, *args, **kwargs):
        """Step 33-36: Execute a job with exception classification,
        exponential backoff retry, max retries, and DLQ on exhaustion."""
        retry_count = _get_retry_count(job_id)
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            _reset_retry(job_id)
            duration = time.time() - start_time
            _record_job_metric(job_id, "success", duration)
            return result
        except TransientError as e:
            if retry_count < self._max_retries:
                delay = _compute_backoff(retry_count)
                _increment_retry(job_id)
                self.logger.warning(
                    f"Transient error in {job_id} (attempt {_get_retry_count(job_id)}/{self._max_retries}): {e}. "
                    f"Retrying in {delay:.1f}s"
                )
                time.sleep(delay)
                return self._safe_run_job(job_id, func, *args, **kwargs)
            else:
                _enqueue_dlq(job_id, str(e))
                _reset_retry(job_id)
                self.logger.error(f"Transient error in {job_id} exceeded max retries ({self._max_retries})")
                duration = time.time() - start_time
                _record_job_metric(job_id, "failed", duration)
        except ConfigurationError as e:
            _enqueue_dlq(job_id, str(e))
            _reset_retry(job_id)
            self.logger.error(f"Configuration error in {job_id}: {e}", exc_info=True)
            duration = time.time() - start_time
            _record_job_metric(job_id, "config_error", duration)
            notifier.notify_critical_error(f"Configuration error in {job_id}: {e}")
        except FatalError as e:
            _enqueue_dlq(job_id, str(e))
            _reset_retry(job_id)
            self.logger.error(f"Fatal error in {job_id}: {e}", exc_info=True)
            duration = time.time() - start_time
            _record_job_metric(job_id, "fatal", duration)

    def start(self):
        if not self._is_running:
            # Step 39: Setup JSON structured logging
            setup_json_logging()
            
            self.scheduler.start()
            self._is_running = True
            self.logger.info("Scheduler started.", extra={"event": "scheduler_started"})
            # ジョブをDBの設定と同期
            self.sync_crawl_jobs()
            # 10分ごとにスケジュール同期ジョブを実行
            if not self.scheduler.get_job("sync_scheduler_jobs"):
                self.scheduler.add_job(
                    self.sync_crawl_jobs, 'interval', minutes=10, id="sync_scheduler_jobs"
                )
            # URL監視ジョブを追加
            self.add_url_monitor_job()
            # メトリクスクリーンアップジョブを追加
            self.add_metrics_cleanup_job()
            # ヘルスチェック・アラート判定ジョブを追加 (60秒毎)
            self.add_health_check_job()
            # 落札結果クロールジョブを追加 (毎日午前2時)
            self.add_award_crawl_job()
            # 発注見通しクロールジョブ (毎週日曜 午前5時)
            self.add_forecast_weekly_crawl_job()
            # 発注見通し集中巡回ジョブ (四半期初め: 1/4/7/10月 午前5時)
            self.add_forecast_quarterly_crawl_job()
            # バックフィルジョブ (毎日午前3時)
            self.add_backfill_job()
            # 毎朝アラート配信ジョブを追加 (毎日午前8時)
            self.add_morning_digest_job()
            # 品質メトリクス収集ジョブを追加 (毎日午前5時30分)
            self.add_quality_metrics_job()
            # 品質アラート評価ジョブを追加 (毎日午前5時45分)
            self.add_quality_alert_evaluation_job()

    def stop(self):
        if self._is_running:
            self.scheduler.shutdown()
            self._is_running = False
            self.logger.info("Scheduler stopped.")

    def add_health_check_job(self):
        """1分ごとにシステムの各コンポーネントをヘルスチェックし、AlertManagerに評価させるジョブを追加"""
        job_id = "system_health_check_job"
        self.scheduler.add_job(
            self._run_health_check,
            'interval',
            seconds=60,
            id=job_id,
            replace_existing=True
        )
        self.logger.info(f"Scheduled system health check job: {job_id} (Every 60s)")

    def _run_health_check(self):
        def _health_check():
            from services.health_checker import HealthChecker, HealthStatus
            from services.alert_manager import AlertManager
            
            checker = HealthChecker()
            alert_manager = AlertManager()
            
            # 各コンポーネントをチェック
            redis_health = checker.check_redis()
            alert_manager.evaluate_and_alert("Redis", redis_health.status == HealthStatus.HEALTHY, redis_health.message)
            
            db_health = checker.check_database()
            alert_manager.evaluate_and_alert("Database", db_health.status == HealthStatus.HEALTHY, db_health.message)
            
            queue_health = checker.check_queue_depth()
            alert_manager.evaluate_and_alert("QueueDepth", queue_health.status != HealthStatus.UNHEALTHY, queue_health.message)
            
            scheduler_health = checker.check_scheduler()
            alert_manager.evaluate_and_alert("Scheduler", scheduler_health.status == HealthStatus.HEALTHY, scheduler_health.message)
        self._safe_run_job("system_health_check_job", _health_check)

    def add_metrics_cleanup_job(self):
        """毎日午前4時に古いメトリクスを自動削除するジョブを追加"""
        job_id = "metrics_cleanup_job"
        self.scheduler.add_job(
            self._run_metrics_cleanup,
            'cron',
            hour=4,
            minute=0,
            id=job_id,
            replace_existing=True
        )
        self.logger.info(f"Scheduled metrics cleanup job: {job_id} (Daily at 04:00)")

    def _run_metrics_cleanup(self):
        def _cleanup():
            from scripts.cleanup_metrics import cleanup_old_metrics
            from config_dir import AppConfig
            config = AppConfig()
            retention_days = config.observability.metrics_retention_days
            cleanup_old_metrics(retention_days)
        self._safe_run_job("metrics_cleanup_job", _cleanup)

    def sync_crawl_jobs(self):
        """
        データベースからアクティブな自治体クロール設定を取得し、スケジュールを自動同期する。
        """
        self.logger.info("Syncing scheduler jobs with database configurations...")
        try:
            with get_db() as session:
                active_configs = session.query(CrawlConfig).filter(CrawlConfig.is_active == True).all()
                active_job_ids = set()

                for config in active_configs:
                    job_id = f"agency_crawl_{config.id}"
                    active_job_ids.add(job_id)
                    
                    # 既に同じ設定のジョブがあるか確認
                    existing_job = self.scheduler.get_job(job_id)
                    
                    # 時系列・曜日の負荷分散（IDに基づく決定論的ジッター）
                    hour_jitter = (config.id % 4) + 2    # 午前2時〜5時
                    minute_jitter = config.id % 60       # 0分〜59分
                    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                    day_jitter = days[config.id % 7]

                    if config.frequency == "hourly":
                        trigger_type = "interval"
                        trigger_args = {"hours": 1}
                    elif config.frequency == "daily":
                        trigger_type = "cron"
                        trigger_args = {"hour": hour_jitter, "minute": minute_jitter}
                    elif config.frequency == "weekly":
                        trigger_type = "cron"
                        trigger_args = {"day_of_week": day_jitter, "hour": hour_jitter, "minute": minute_jitter}
                    else:
                        trigger_type = "cron"
                        trigger_args = {"hour": hour_jitter, "minute": minute_jitter}

                    # 新規追加、または更新がある場合は再登録
                    # (簡略化のため、既存ジョブを一旦削除して追加)
                    if existing_job:
                        self.scheduler.remove_job(job_id)

                    self.scheduler.add_job(
                        trigger_agency_crawl,
                        trigger_type,
                        args=[config.id],
                        id=job_id,
                        replace_existing=True,
                        **trigger_args
                    )
                    self.logger.info(f"Scheduled job: {job_id} ({config.frequency}) for Agency: {config.agency.name}")

                # 不要になった（非アクティブ化した・削除された）ジョブのクリーニング
                for job in list(self.scheduler.get_jobs()):
                    if job.id.startswith("agency_crawl_") and job.id not in active_job_ids:
                        self.scheduler.remove_job(job.id)
                        self.logger.info(f"Removed inactive job: {job.id}")

        except Exception as e:
            self.logger.error(f"Failed to sync scheduler jobs: {e}", exc_info=True)

    def add_crawl_job(self, job_id="daily_crawl", interval="DAILY", hour=3, minute=0, url=None):
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        job_kwargs = {'id': job_id}

        if interval == "HOURLY":
            self.scheduler.add_job(
                self._run_with_notification, 'interval', hours=1, 
                kwargs={'url': url}, **job_kwargs
            )
        elif interval == "DAILY":
            self.scheduler.add_job(
                self._run_with_notification, 'cron', hour=hour, minute=minute,
                kwargs={'url': url}, **job_kwargs
            )
        elif interval == "WEEKLY":
            self.scheduler.add_job(
                self._run_with_notification, 'cron', day_of_week='mon', hour=hour, minute=minute,
                kwargs={'url': url}, **job_kwargs
            )
        else:
            raise ValueError(f"Unsupported interval: {interval}")
        
        self.logger.info(f"Job {job_id} scheduled with interval {interval}")

    def _run_with_notification(self, url=None):
        def _crawl():
            result = execute_crawl()
            if result and result.get('new_count', 0) > 0:
                notifier.notify_new_bids(result['new_count'], url or "multiple URLs")
        self._safe_run_job("daily_crawl", _crawl)

    def list_jobs(self):
        return self.scheduler.get_jobs()

    def remove_job(self, job_id):
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logging.info(f"Job {job_id} removed.")

    def add_url_monitor_job(self):
        """
        URL監視ジョブをスケジュールに追加する。
        頻度はCrawlConfigなどの設定から取得することを検討し、現在はデフォルトで毎日午前1時に設定。
        """
        job_id = "url_monitor_job"
        
        # 将来的には設定ファイルやDBから取得できるように拡張する
        # 現時点ではデフォルトのスケジュールを適用
        hour = 1
        minute = 0
        
        self.scheduler.add_job(
            self._run_url_monitor_async,
            'cron',
            hour=hour,
            minute=minute,
            id=job_id,
            replace_existing=True
        )
        self.logger.info(f"Scheduled URL monitor job: {job_id} (Daily at {hour:02d}:{minute:02d})")

    def add_award_crawl_job(self):
        """落札結果クロールジョブを毎日午前2時に実行するように登録する。"""
        job_id = "award_crawl_job"
        self.scheduler.add_job(
            self._run_award_crawl_async,
            'cron',
            hour=2,
            minute=0,
            id=job_id,
            replace_existing=True,
        )
        self.logger.info(f"Scheduled award crawl job: {job_id} (Daily at 02:00)")

    def add_forecast_weekly_crawl_job(self):
        """発注見通しクロールジョブを毎週日曜午前5時に実行するように登録する。"""
        job_id = "forecast_weekly_crawl_job"
        self.scheduler.add_job(
            self._run_forecast_crawl_async,
            'cron',
            day_of_week='sun',
            hour=5,
            minute=0,
            id=job_id,
            replace_existing=True,
        )
        self.logger.info(f"Scheduled forecast weekly crawl job: {job_id} (Weekly Sun 05:00)")

    def add_forecast_quarterly_crawl_job(self):
        """発注見通し集中巡回ジョブを四半期の初め（1/4/7/10月）午前5時に実行する。"""
        job_id = "forecast_quarterly_crawl_job"
        self.scheduler.add_job(
            self._run_forecast_crawl_async,
            'cron',
            month='1,4,7,10',
            day=1,
            hour=5,
            minute=0,
            id=job_id,
            replace_existing=True,
        )
        self.logger.info(f"Scheduled forecast quarterly crawl job: {job_id} (Jan/Apr/Jul/Oct 1st 05:00)")

    def _run_forecast_crawl_async(self):
        """発注見通し巡回を実行するラッパー。"""
        def _forecast_crawl():
            from services.forecast_notification_service import ForecastNotificationService
            summary = crawl_all_forecasts()
            logger.info(f"Forecast crawl completed. Stored: {summary.get('total_stored', 0)}")
            try:
                with get_db() as session:
                    notifier = ForecastNotificationService(session)
                    notifier.notify_crawl_summary(summary)
            except Exception as e:
                logger.warning(f"Forecast crawl notification skipped: {e}")
        self._safe_run_job("forecast_crawl_job", _forecast_crawl)

    def add_morning_digest_job(self):
        """毎朝アラート配信ジョブを毎日午前8時に実行するように登録する。"""
        job_id = "morning_digest_job"
        self.scheduler.add_job(
            self._run_morning_digest_async,
            'cron',
            hour=8,
            minute=0,
            id=job_id,
            replace_existing=True,
        )
        self.logger.info(f"Scheduled morning digest job: {job_id} (Daily at 08:00)")

    def _run_morning_digest_async(self):
        """朝のダイジェスト通知を実行するラッパー。"""
        def _morning_digest():
            from services.morning_digest_service import MorningDigestService
            with get_db() as session:
                service = MorningDigestService(session)
                service.run_morning_digest()
            logger.info("Morning digest job completed.")
        self._safe_run_job("morning_digest_job", _morning_digest)

    def add_quality_metrics_job(self):
        """品質メトリクス収集ジョブを毎日午前5時30分に登録する。"""
        job_id = "collect_quality_metrics_job"
        self.scheduler.add_job(
            self._run_collect_quality_metrics_async,
            'cron',
            hour=5,
            minute=30,
            id=job_id,
            replace_existing=True,
        )
        self.logger.info(f"Scheduled quality metrics collection job: {job_id} (Daily at 05:30)")

    def _run_collect_quality_metrics_async(self):
        """品質メトリクス収集を実行するラッパー。"""
        def _collect_metrics():
            from scripts.collect_quality_metrics import run as collect_metrics
            collect_metrics()
            self.logger.info("Quality metrics collection job completed.")
        self._safe_run_job("collect_quality_metrics_job", _collect_metrics)

    def add_quality_alert_evaluation_job(self):
        """品質アラート評価ジョブを毎日午前5時45分に登録する。"""
        job_id = "evaluate_quality_alerts_job"
        self.scheduler.add_job(
            self._run_evaluate_quality_alerts_async,
            'cron',
            hour=5,
            minute=45,
            id=job_id,
            replace_existing=True,
        )
        self.logger.info(f"Scheduled quality alert evaluation job: {job_id} (Daily at 05:45)")

    def _run_evaluate_quality_alerts_async(self):
        """品質アラート評価を実行するラッパー。"""
        def _evaluate_alerts():
            from scripts.evaluate_quality_alerts import run as evaluate_alerts
            evaluate_alerts()
            self.logger.info("Quality alert evaluation job completed.")
        self._safe_run_job("evaluate_quality_alerts_job", _evaluate_alerts)

    def add_backfill_job(self):
        """バックフィルジョブを追加（毎日午前3時実行）"""
        job_id = "backfill_job"
        self.scheduler.add_job(
            self._run_backfill_async,
            'cron',
            hour=3,
            minute=0,
            id=job_id,
            replace_existing=True,
        )
        self.logger.info(f"Scheduled backfill job: {job_id} (Daily at 03:00)")

    def _run_backfill_async(self):
        """バックフィルジョブを実行するラッパー"""
        def _backfill():
            from services.backfill_service import BackfillService
            from database.models import BackfillJob, BackfillJobStatus
            from database.session import get_db
            
            service = BackfillService()
            
            # 失敗済みジョブのリトライ
            failed_jobs = service.list_jobs(status="failed")
            for job in failed_jobs:
                if job.retry_count < self._max_retries:
                    service.retry_job(job.id)
                    self.logger.info(f"Retrying failed backfill job: {job.id}")
            
            # 保留中ジョブの実行（直近7日以内に実行済みの同一機関ジョブはスキップ）
            pending_jobs = service.list_jobs(status="pending", limit=50)
            for job in pending_jobs:
                with get_db() as db:
                    recent_done = db.query(BackfillJob).filter(
                        BackfillJob.agency_id == job.agency_id,
                        BackfillJob.start_date == job.start_date,
                        BackfillJob.end_date == job.end_date,
                        BackfillJob.status == BackfillJobStatus.DONE,
                        BackfillJob.finished_at >= datetime.utcnow() - timedelta(days=7),
                    ).first()
                    
                    if recent_done:
                        self.logger.info(f"Skipping job {job.id}: similar job done recently")
                        continue
                
                service.run_job(job.id)
                self.logger.info(f"Executed backfill job: {job.id}")
            
            logger.info("Backfill job batch completed.")
        self._safe_run_job("backfill_job", _backfill)

    def _run_award_crawl_async(self):
        """非同期フラグの無いrun_award_crawlを呼ぶラッパー。"""
        def _award_crawl():
            result = run_award_crawl()
            logger.info(f"Award crawl async result: {result}")
        self._safe_run_job("award_crawl_job", _award_crawl)

    def _run_url_monitor_async(self):
        """
        非同期関数である run_url_monitor を同期的なスケジューラから呼び出すためのラッパー。
        """
        def _url_monitor():
            import asyncio
            asyncio.run(run_url_monitor())
        self._safe_run_job("url_monitor_job", _url_monitor)

# Global instance
scheduler_manager = SchedulerManager()


def retry_dlq_jobs(job_ids: list | None = None) -> dict:
    """Step 36: Manually retry jobs from the Dead Letter Queue.
    
    Args:
        job_ids: If provided, only retry these job IDs. Otherwise retry all.
    
    Returns:
        Dict with 'retried', 'failed', 'errors' keys.
    """
    if not _DEAD_LETTER_QUEUE_PATH.exists():
        logger.info("DLQ file not found; nothing to retry.")
        return {"retried": 0, "failed": 0, "errors": []}
    
    try:
        with open(_DEAD_LETTER_QUEUE_PATH, "r") as f:
            entries = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to read DLQ file: {e}", exc_info=True)
        return {"retried": 0, "failed": 0, "errors": [str(e)]}
    
    if job_ids:
        entries = [e for e in entries if e["job_id"] in job_ids]
    
    results = {"retried": 0, "failed": 0, "errors": []}
    remaining = []
    
    for entry in entries:
        job_id = entry["job_id"]
        try:
            if job_id == "daily_crawl":
                execute_crawl()
            elif job_id == "forecast_crawl_job":
                crawl_all_forecasts()
            elif job_id == "morning_digest_job":
                from services.morning_digest_service import MorningDigestService
                with get_db() as session:
                    MorningDigestService(session).run_morning_digest()
            elif job_id == "backfill_job":
                from services.backfill_service import BackfillService
                BackfillService().run()
            elif job_id == "award_crawl_job":
                run_award_crawl()
            elif job_id == "url_monitor_job":
                import asyncio
                asyncio.run(run_url_monitor())
            elif job_id == "metrics_cleanup_job":
                from scripts.cleanup_metrics import cleanup_old_metrics
                from config_dir import AppConfig
                cleanup_old_metrics(AppConfig().observability.metrics_retention_days)
            elif job_id == "system_health_check_job":
                scheduler_manager._safe_run_job("system_health_check_job", 
                    lambda: None)  # Will re-run via health check itself
            else:
                logger.warning(f"Unknown job_id in DLQ: {job_id}")
                results["failed"] += 1
                results["errors"].append(f"Unknown job: {job_id}")
                remaining.append(entry)
                continue
            
            results["retried"] += 1
            logger.info(f"Successfully retried DLQ job: {job_id}")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{job_id}: {e}")
            logger.error(f"Failed to retry DLQ job {job_id}: {e}", exc_info=True)
            remaining.append(entry)
    
    # Save remaining (still-failed) entries back to DLQ
    try:
        with open(_DEAD_LETTER_QUEUE_PATH, "w") as f:
            json.dump(remaining, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to update DLQ file: {e}", exc_info=True)
    
    return results

