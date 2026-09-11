"""バックフィル実行サービス

バックフィルジョブの作成・実行・管理を行うサービス
"""
import asyncio
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from database.session import get_db
from database.models import (
    Agency,
    BidSource,
    BackfillJob,
    BackfillJobStatus,
    BackfillJobLog,
    CrawlConfig,
    AgencyCategory,
)
from services.bid_storage_service import BidStorageService
from crawler.generic_crawler import GenericCrawler
from crawler.geps_crawler import GEPSCrawler
from crawler.config_driven_crawler import ConfigDrivenCrawler
from notifier import notify_backfill_done, notify_backfill_error

logger = logging.getLogger(__name__)


class BackfillService:
    """バックフィル実行サービス"""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.storage = BidStorageService()

    @contextmanager
    def _session(self):
        """DBセッションを取得するコンテキストマネージャ"""
        db = next(get_db())
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_job(
        self,
        agency_id: int,
        years: int = 2,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> BackfillJob:
        """バックフィルジョブを作成

        Args:
            agency_id: 対象機関ID
            years: 遡及年数（start_date/end_date 未指定時）
            start_date: 開始日（指定時は years を無視）
            end_date: 終了日（指定時は years を無視）

        Returns:
            作成された BackfillJob
        """
        with self._session() as db:
            # 期間計算
            if start_date is None or end_date is None:
                effective_end = end_date or datetime.now(timezone.utc).date()
                effective_start = start_date or (effective_end - timedelta(days=years * 365))
            else:
                effective_start = start_date
                effective_end = end_date

            # 重複チェック: 同一機関・同一期間で pending/running がある場合は作成しない
            existing = db.query(BackfillJob).filter(
                BackfillJob.agency_id == agency_id,
                BackfillJob.start_date == effective_start,
                BackfillJob.end_date == effective_end,
                BackfillJob.status.in_([BackfillJobStatus.PENDING, BackfillJobStatus.RUNNING]),
            ).first()

            if existing:
                logger.info(f"Duplicate job skipped: agency_id={agency_id}, job_id={existing.id}")
                db.expunge(existing)
                return existing

            # ジョブ作成
            job = BackfillJob(
                agency_id=agency_id,
                start_date=effective_start,
                end_date=effective_end,
                status=BackfillJobStatus.PENDING,
            )
            db.add(job)
            db.flush()

            self._log(db, job.id, "create", f"Job created for agency_id={agency_id}, range={effective_start}~{effective_end}", "INFO")

            logger.info(f"Created backfill job: id={job.id}, agency_id={agency_id}")
            db.expunge(job)
            return job

    def run_job(self, job_id: int) -> BackfillJob:
        """バックフィルジョブを実行

        Args:
            job_id: 実行するジョブID

        Returns:
            更新された BackfillJob
        """
        with self._session() as db:
            job = db.query(BackfillJob).get(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            if job.status == BackfillJobStatus.RUNNING:
                logger.warning(f"Job already running: {job_id}")
                return job

            if job.status == BackfillJobStatus.DONE:
                logger.info(f"Job already done: {job_id}")
                return job

            # ステータスを running に更新
            job.status = BackfillJobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            db.commit()

            self._log(db, job.id, "start", f"Job started for agency_id={job.agency_id}", "INFO")

            # 機関情報取得
            agency = db.query(Agency).get(job.agency_id)
            if not agency:
                raise ValueError(f"Agency not found: {job.agency_id}")

            # クローラー種別判定と実行
            crawler = self._get_crawler_for_agency(db, agency)
            if not crawler:
                raise ValueError(f"No suitable crawler for agency: {agency.name}")

            # 日付範囲指定でクロール実行
            fetched_items = self._run_crawl(crawler, agency, job.start_date, job.end_date)

            # 結果を保存
            new_count = 0
            updated_count = 0
            error_count = 0

            for item in fetched_items:
                try:
                    bid = self.storage.save_bid(item)
                    if bid:
                        # 新規か更新か判定（簡易的に created_at と updated_at で判定）
                        if bid.created_at == bid.updated_at:
                            new_count += 1
                        else:
                            updated_count += 1
                except Exception as e:
                    error_count += 1
                    self._log(db, job.id, "save_error", f"Failed to save bid: {e}", "ERROR")

            # ジョブ完了
            job.fetched_count = len(fetched_items)
            job.new_count = new_count
            job.updated_count = updated_count
            job.error_count = error_count
            job.finished_at = datetime.now(timezone.utc)

            start_time = job.started_at
            duration = (job.finished_at - start_time).total_seconds() if start_time else None

            if error_count > 0 and new_count == 0 and updated_count == 0:
                job.status = BackfillJobStatus.FAILED
                job.error_message = f"All {error_count} items failed to save"
                self._log(db, job.id, "complete", f"Job failed: {job.error_message}", "ERROR")
            else:
                job.status = BackfillJobStatus.DONE
                self._log(db, job.id, "complete", f"Job completed: fetched={len(fetched_items)}, new={new_count}, updated={updated_count}, errors={error_count}", "INFO")

            db.commit()
            
            # セッション外で通知送信（Agency情報が必要）
            agency_name = agency.name
            job_status = job.status.value
            fetched = job.fetched_count
            new_c = job.new_count
            updated_c = job.updated_count

            logger.info(f"Job {job_id} completed: status={job_status}, fetched={fetched}")

            # 通知送信（非同期で実行）
            try:
                if job_status == "done":
                    notify_backfill_done(job_id, agency_name, fetched, new_c, updated_c, job_status, duration)
                else:
                    notify_backfill_error(job_id, agency_name, job.error_message or "Unknown error")
            except Exception as e:
                logger.warning(f"Notification failed: {e}")

            return job

    def _get_crawler_for_agency(self, db, agency: Agency):
        """機関に適したクローラーを取得"""
        # BidSource から source_type を確認
        source = db.query(BidSource).filter(
            BidSource.prefecture_id == agency.id,
            BidSource.is_active == True,
        ).first()

        if source:
            if source.source_type == "geps":
                return GEPSCrawler(start_date=None, end_date=None)
            elif source.source_type == "web":
                parser_type = source.parser_type or "heuristic"
                return GenericCrawler(parser_type=parser_type, start_date=None, end_date=None)

        # CrawlConfig から判定
        config = db.query(CrawlConfig).filter(
            CrawlConfig.agency_id == agency.id,
            CrawlConfig.is_active == True,
        ).first()

        if config:
            if "geps" in config.target_url.lower() or "geps" in (config.parser_type or "").lower():
                return GEPSCrawler(start_date=None, end_date=None)
            else:
                return GenericCrawler(parser_type=config.parser_type or "heuristic", start_date=None, end_date=None)

        # デフォルト: GenericCrawler
        return GenericCrawler(parser_type="heuristic", start_date=None, end_date=None)

    def _run_crawl(self, crawler, agency: Agency, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """クローラーで日付範囲指定巡回を実行"""
        # 一時的に日付範囲を設定
        original_start = crawler.start_date
        original_end = crawler.end_date
        crawler.start_date = start_date
        crawler.end_date = end_date

        try:
            # クローラー種別に応じて実行
            if isinstance(crawler, GEPSCrawler):
                # GEPSの場合、検索クエリを構築
                query = agency.name or ""
                # 非同期実行
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    results = loop.run_until_complete(
                        crawler.search_bids(query=query, start_date=start_date, end_date=end_date)
                    )
                finally:
                    loop.close()
                return results

            elif isinstance(crawler, GenericCrawler):
                # GenericCrawler の場合、crawl_site を呼び出し
                # 対象URLを決定
                target_url = self._get_target_url(agency)
                if not target_url:
                    return []

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    results = loop.run_until_complete(
                        crawler.crawl_site(target_url, agency.name or "不明", start_date, end_date)
                    )
                finally:
                    loop.close()

                # CrawlResult を dict に変換
                return [self._crawl_result_to_dict(r) for r in results]

            else:
                # ConfigDrivenCrawler 等
                return []

        finally:
            crawler.start_date = original_start
            crawler.end_date = original_end

    def _get_target_url(self, agency: Agency) -> Optional[str]:
        """機関のクロール対象URLを取得"""
        with self._session() as db:
            source = db.query(BidSource).filter(
                BidSource.prefecture_id == agency.id,
                BidSource.is_active == True,
            ).first()
            if source:
                return source.url

            config = db.query(CrawlConfig).filter(
                CrawlConfig.agency_id == agency.id,
                CrawlConfig.is_active == True,
            ).first()
            if config:
                return config.target_url

            return agency.base_url

    def _crawl_result_to_dict(self, result) -> Dict[str, Any]:
        """CrawlResult を保存用 dict に変換"""
        return {
            "title": getattr(result, "title", "未取得"),
            "organization": getattr(result, "agency_name", "未取得"),
            "budget": getattr(result, "budget", ""),
            "deadline": getattr(result, "deadline", ""),
            "source_url": getattr(result, "url", ""),
            "project_name": getattr(result, "title", "未取得"),
            "prefecture_code": getattr(result, "prefecture_code", ""),
            "qualifications": getattr(result, "qualifications", None),
            "deliverables": getattr(result, "deliverables", None),
            "announcement_date": getattr(result, "announcement_date", None),
        }

    def _log(self, db, job_id: int, step: str, message: str, level: str = "INFO"):
        """実行ログを記録"""
        log = BackfillJobLog(
            job_id=job_id,
            step=step,
            message=message,
            level=level,
        )
        db.add(log)
        db.flush()

    # === 便利メソッド ===

    def get_job(self, job_id: int) -> Optional[BackfillJob]:
        """ジョブ取得"""
        with self._session() as db:
            job = db.query(BackfillJob).get(job_id)
            if job:
                db.expunge(job)
            return job

    def list_jobs(
        self,
        agency_id: Optional[int] = None,
        status: Optional[BackfillJobStatus] = None,
        limit: int = 100,
    ) -> List[BackfillJob]:
        """ジョブ一覧取得"""
        with self._session() as db:
            query = db.query(BackfillJob)
            if agency_id:
                query = query.filter(BackfillJob.agency_id == agency_id)
            if status:
                query = query.filter(BackfillJob.status == status)
            jobs = query.order_by(BackfillJob.created_at.desc()).limit(limit).all()
            for job in jobs:
                db.expunge(job)
            return jobs

    def retry_job(self, job_id: int) -> BackfillJob:
        """失敗ジョブをリトライ"""
        with self._session() as db:
            job = db.query(BackfillJob).get(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            if job.status not in [BackfillJobStatus.FAILED, BackfillJobStatus.PENDING]:
                raise ValueError(f"Cannot retry job with status: {job.status.value}")

            job.status = BackfillJobStatus.PENDING
            job.retry_count += 1
            job.error_message = None
            db.commit()

            db.expunge(job)

        # セッションを分けて実行（run_job 内で新しいセッションを使うため）
        return self.run_job(job_id)

    def cancel_job(self, job_id: int) -> BackfillJob:
        """実行中ジョブをキャンセル

        RUNNING 状態のジョブのみキャンセル可能
        """
        with self._session() as db:
            job = db.query(BackfillJob).get(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            if job.status != BackfillJobStatus.RUNNING:
                raise ValueError(f"Cannot cancel job with status: {job.status.value}. Only RUNNING jobs can be cancelled.")

            agency_id = job.agency_id
            job.status = BackfillJobStatus.FAILED
            job.error_message = "Cancelled by user"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            self._log(db, job.id, "cancel", "Job cancelled by user", "WARNING")

            # 通知送信
            try:
                agency = db.query(Agency).get(agency_id)
                if agency:
                    notify_backfill_error(job_id, agency.name, "Cancelled by user")
            except Exception as e:
                logger.warning(f"Cancel notification failed: {e}")

            db.expunge(job)
            return job