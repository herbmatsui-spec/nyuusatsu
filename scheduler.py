import os
import logging
from datetime import datetime
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

logger = logging.getLogger(__name__)

jobstores = {
    'default': SQLAlchemyJobStore(url=DATABASE_URL)
}

notifier = Notifier()

class SchedulerManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler(jobstores=jobstores)
        self._is_running = False
        self.logger = logging.getLogger(__name__)

    def start(self):
        if not self._is_running:
            self.scheduler.start()
            self._is_running = True
            self.logger.info("Scheduler started.")
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
        try:
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
            
        except Exception as e:
            self.logger.error(f"Health check execution failed: {e}", exc_info=True)

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
        try:
            from scripts.cleanup_metrics import cleanup_old_metrics
            from config_dir import AppConfig
            config = AppConfig()
            retention_days = config.observability.metrics_retention_days
            cleanup_old_metrics(retention_days)
        except Exception as e:
            self.logger.error(f"Metrics cleanup job failed: {e}", exc_info=True)

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
        try:
            # execute_crawl() の代わりに、DBの設定に基づいた統合的な巡回処理を呼び出す
            # ここでは既存の execute_crawl を維持しつつ、将来的に trigger_agency_crawl のループに統合可能
            result = execute_crawl()
            if result and result.get('new_count', 0) > 0:
                notifier.notify_new_bids(result['new_count'], url or "multiple URLs")
        except Exception as e:
            self.logger.error(f"Crawl job failed: {e}")
            notifier.notify_critical_error(str(e))

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
        try:
            from services.forecast_notification_service import ForecastNotificationService
            summary = crawl_all_forecasts()
            logger.info(f"Forecast crawl completed. Stored: {summary.get('total_stored', 0)}")
            try:
                with get_db() as session:
                    notifier = ForecastNotificationService(session)
                    notifier.notify_crawl_summary(summary)
            except Exception as e:
                logger.warning(f"Forecast crawl notification skipped: {e}")
        except Exception as e:
            logger.error(f"Forecast crawl job failed: {e}", exc_info=True)

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
        try:
            from services.morning_digest_service import MorningDigestService
            from database.session import get_db
            with get_db() as session:
                service = MorningDigestService(session)
                service.run_morning_digest()
            logger.info("Morning digest job completed.")
        except Exception as e:
            logger.error(f"Morning digest job failed: {e}", exc_info=True)

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
        try:
            from scripts.collect_quality_metrics import run as collect_metrics
            collect_metrics()
            self.logger.info("Quality metrics collection job completed.")
        except Exception as e:
            self.logger.error(f"Quality metrics collection job failed: {e}", exc_info=True)

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
        try:
            from scripts.evaluate_quality_alerts import run as evaluate_alerts
            evaluate_alerts()
            self.logger.info("Quality alert evaluation job completed.")
        except Exception as e:
            self.logger.error(f"Quality alert evaluation job failed: {e}", exc_info=True)

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
        try:
            from services.backfill_service import BackfillService
            service = BackfillService()
            
            # 失敗済みジョブのリトライ
            failed_jobs = service.list_jobs(status="failed")
            for job in failed_jobs:
                if job.retry_count < 3:
                    service.retry_job(job.id)
                    self.logger.info(f"Retrying failed backfill job: {job.id}")
            
            # 保留中ジョブの実行（直近7日以内に実行済みの同一機関ジョブはスキップ）
            pending_jobs = service.list_jobs(status="pending", limit=50)
            for job in pending_jobs:
                # 同一機関・同一期間で直近7日以内に完了したジョブがあるかチェック
                from datetime import timedelta
                from database.models import BackfillJob, BackfillJobStatus
                from database.session import get_db
                
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
        except Exception as e:
            logger.error(f"Backfill job batch failed: {e}", exc_info=True)

    def _run_award_crawl_async(self):
        """非同期フラグの無いrun_award_crawlを呼ぶラッパー。"""
        try:
            result = run_award_crawl()
            logger.info(f"Award crawl async result: {result}")
        except Exception as e:
            logger.error(f"Award crawl job failed: {e}")

    def _run_url_monitor_async(self):
        """
        非同期関数である run_url_monitor を同期的なスケジューラから呼び出すためのラッパー。
        """
        try:
            import asyncio
            asyncio.run(run_url_monitor())
        except Exception as e:
            self.logger.error(f"URL monitor job failed: {e}", exc_info=True)

# Global instance
scheduler_manager = SchedulerManager()

