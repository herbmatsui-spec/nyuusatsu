import os
import logging
from typing import List, Dict, Any, Optional
from rq import Queue

from database.session import get_db
from database.repositories.pdf_repository import PDFRepository
from database.repositories.agency_repository import AgencyRepository
from crawler.generic_crawler import GenericCrawler
from crawler.downloader import PDFDownloader
from crawler.models.crawl_result import CrawlResult

# Redis接続は共通モジュールから取得 (protocol=2 設定済み)
from database.redis_conn import redis_conn

logger = logging.getLogger("CrawlerPipeline")
try:
    redis_conn.ping()
    logger.info("Successfully connected to Redis.")
except Exception as e:
    logger.warning(f"Redis connection failed (queues disabled): {e}")

# RQ キューの初期化 (Redis 未接続時は None にフォールバック)
if redis_conn:
    crawl_queue = Queue("crawl_tasks", connection=redis_conn)
    download_queue = Queue("download_tasks", connection=redis_conn)
    analysis_queue = Queue("analysis_tasks", connection=redis_conn)
    notification_queue = Queue("notification_tasks", connection=redis_conn)
else:
    crawl_queue = None
    download_queue = None
    analysis_queue = None
    notification_queue = None


# -----------------------------------------------------------------------------
# Background Tasks (RQ Workers will run these)
# -----------------------------------------------------------------------------

def download_pdf_task(agency_id: int, title: str, url: str, publish_date: str) -> Optional[int]:
    """
    バックグラウンドで指定されたURLからPDFをダウンロードし、DBにメタデータを記録するタスク。
    """
    from utils.log_context import new_trace_id, set_pipeline_stage
    from services.metrics_collector import BufferedMetricsCollector
    
    trace_id = new_trace_id()
    set_pipeline_stage("download")
    
    logger.info(f"Starting background download task for URL: {url}", extra={"agency_id": agency_id, "trace_id": trace_id})
    
    downloader = PDFDownloader()
    
    # 処理時間を測定
    with BufferedMetricsCollector.measure("download", "duration_ms", labels={"agency_id": agency_id}, trace_id=trace_id):
        success, file_path, sha256, error_msg = downloader.download(url)
    
    if not success:
        logger.error(f"Download failed for {url}: {error_msg}", extra={"agency_id": agency_id, "trace_id": trace_id})
        BufferedMetricsCollector.record("download", "success", 0.0, labels={"agency_id": agency_id, "error": error_msg}, trace_id=trace_id)
        BufferedMetricsCollector.flush()
        return None

    BufferedMetricsCollector.record("download", "success", 1.0, labels={"agency_id": agency_id}, trace_id=trace_id)

    # ファイルサイズの取得
    file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0
    BufferedMetricsCollector.record("download", "file_size_bytes", float(file_size), labels={"agency_id": agency_id}, trace_id=trace_id)

    with get_db() as session:
        pdf_repo = PDFRepository(session)
        
        # SHA-256 での重複排除チェック
        existing_doc = pdf_repo.get_by_sha256(sha256)
        if existing_doc:
            logger.info(f"Duplicate PDF detected by hash. Skipping database insertion. File: {file_path}")
            BufferedMetricsCollector.record("download", "duplicate_hash", 1.0, labels={"agency_id": agency_id}, trace_id=trace_id)
            BufferedMetricsCollector.flush()
            # 一時ダウンロードファイルの削除
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to remove duplicate temp file {file_path}: {e}")
            return existing_doc.id

        # 重複がなければDBに保存
        filename = os.path.basename(file_path)
        pdf_doc = pdf_repo.create(
            url=url,
            filename=filename,
            sha256=sha256,
            file_size=file_size,
            agency_id=agency_id
        )
        session.commit()
        logger.info(f"Saved PDF document to DB with ID: {pdf_doc.id}, file: {filename}", extra={"agency_id": agency_id, "trace_id": trace_id})
        
        # Archive hook: PDFを魚拓保存
        try:
            from services.archive_service import ArchiveService
            archive_service = ArchiveService(session)
            archive_service.download_and_store(
                url=url,
                bid_id=pdf_doc.id,
                file_type="pdf",
                filename=filename,
            )
        except Exception as exc:
            logger.warning("Archive failed for %s: %s", url, exc)
        
        BufferedMetricsCollector.flush()

        # Phase 5: LLM解析タスクのエンキュー
        analysis_queue.enqueue(
            analyze_pdf_task,
            pdf_doc.id,
            file_path,
            url,
            agency_id,
            job_timeout=180,
            result_ttl=86400,
            kwargs={"parent_trace_id": trace_id}
        )
        
        return pdf_doc.id


def analyze_pdf_task(pdf_document_id: int, file_path: str, url: str, agency_id: Optional[int], parent_trace_id: Optional[str] = None) -> Optional[int]:
    """
    バックグラウンドでPDFをテキスト抽出し、LLM要件定義解析を行い、Bid/Matching レコードを作成するタスク。
    """
    import json
    from services.bid_analysis_service import BidAnalysisService
    from utils.log_context import set_trace_id, set_pipeline_stage
    from services.metrics_collector import BufferedMetricsCollector
    
    if parent_trace_id:
        set_trace_id(parent_trace_id)
    set_pipeline_stage("analysis")
    
    logger.info(f"Starting background analysis task for PDF doc ID: {pdf_document_id}", extra={"agency_id": agency_id})
    
    trace_id = parent_trace_id or ""

    with get_db() as session:
        analysis_service = BidAnalysisService(session)
        try:
            # 処理時間を測定
            with BufferedMetricsCollector.measure("analysis", "duration_ms", labels={"agency_id": agency_id}, trace_id=trace_id):
                bid = analysis_service.analyze_and_save(file_path, url, agency_id)
                
            session.commit()
            logger.info(f"Analysis saved to DB. Bid ID: {bid.id}. Enqueuing notification task...")
            
            BufferedMetricsCollector.record("analysis", "success", 1.0, labels={"agency_id": agency_id}, trace_id=trace_id)

            # 通知タスクのエンキュー
            if not os.getenv("SKIP_NOTIFICATION"):
                from utils.log_context import get_log_context
                ctx = get_log_context()
                notification_queue.enqueue(
                    send_new_bid_notification_task,
                    bid.id,
                    job_timeout=30,
                    kwargs={"parent_trace_id": ctx.get("trace_id")}
                )
                BufferedMetricsCollector.record("analysis", "notification_enqueued", 1.0, labels={"agency_id": agency_id}, trace_id=trace_id)
            else:
                logger.info("Notification skipped (SKIP_NOTIFICATION is set)")
            
            BufferedMetricsCollector.flush()

            # クリーンアップ: ダウンロードされた一時PDFファイルの削除
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up temporary PDF file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temp file {file_path}: {e}")
                
            return bid.id
        except Exception as e:
            logger.error(f"Error during LLM analysis/save for PDF doc {pdf_document_id}: {e}", exc_info=True)
            BufferedMetricsCollector.record("analysis", "success", 0.0, labels={"agency_id": agency_id, "error": str(type(e).__name__)}, trace_id=trace_id)
            BufferedMetricsCollector.flush()
            return None


def send_new_bid_notification_task(bid_id: int, parent_trace_id: Optional[str] = None):
    """
    バックグラウンドで新着入札案件のSlack/LINE通知を送信するタスク。
    """
    import json
    import requests
    from database.models import Bid
    from database.models.crawl import SystemSetting
    from utils.log_context import set_trace_id, set_pipeline_stage
    
    if parent_trace_id:
        set_trace_id(parent_trace_id)
    set_pipeline_stage("notification")
    
    logger.info(f"Starting background notification task for Bid ID: {bid_id}")
    
    with get_db() as session:
        bid = session.get(Bid, bid_id)
        if not bid:
            logger.error(f"Bid not found for ID: {bid_id}")
            return
            
        def get_setting(key: str, default: str = "") -> str:
            setting = session.query(SystemSetting).filter(SystemSetting.key == key).first()
            return setting.value if setting else os.getenv(key.upper(), default)

        slack_webhook = get_setting("slack_webhook_url", "")
        line_token = get_setting("line_token", "")
        line_user_id = get_setting("line_user_id", "")
        
        # 参加資格をリストからフォーマット
        quals_str = bid.qualifications
        try:
            quals_list = json.loads(bid.qualifications)
            if isinstance(quals_list, list):
                quals_str = "\n".join([f"  - {q}" for q in quals_list])
        except Exception:
            pass

        message = (
            f"🔔 【新着入札案件検知】\n"
            f"■ 発注機関: {bid.organization_name}\n"
            f"■ 案件名: {bid.filename}\n"
            f"■ 予算上限: {bid.budget}\n"
            f"■ 納期/工期: {bid.deadline}\n"
            f"■ 成果物: {bid.deliverables}\n"
            f"■ 参加資格:\n{quals_str}\n"
            f"■ 仕様書URL: {bid.source_url or '記載なし'}\n"
        )

        
        # Slackへ通知
        if slack_webhook:
            try:
                res = requests.post(slack_webhook, json={"text": message}, timeout=10)
                res.raise_for_status()
                logger.info("Slack notification sent successfully.")
            except Exception as e:
                logger.error(f"Failed to send Slack notification: {e}")
                
        # LINEへ通知
        if line_token:
            try:
                if line_user_id:
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {line_token}"
                    }
                    payload = {
                        "to": line_user_id,
                        "messages": [{"type": "text", "text": message}]
                    }
                    res = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload, timeout=10)
                else:
                    headers = {"Authorization": f"Bearer {line_token}"}
                    res = requests.post("https://notify-api.line.me/api/notify", headers=headers, data={"message": message}, timeout=10)
                res.raise_for_status()
                logger.info("LINE notification sent successfully.")
            except Exception as e:
                logger.error(f"Failed to send LINE notification: {e}")



async def crawl_agency_async(crawl_config_id: int) -> List[Dict[str, Any]]:
    """
    指定されたクロール設定IDに基づき、非同期で対象サイトを巡回してリンクを抽出する。
    """
    from utils.log_context import new_trace_id, set_pipeline_stage
    trace_id = new_trace_id()
    set_pipeline_stage("crawl")
    
    with get_db() as session:
        agency_repo = AgencyRepository(session)
        config = agency_repo.get_config_by_id(crawl_config_id)
        if not config or not config.is_active:
            logger.warning(f"Active CrawlConfig not found for ID: {crawl_config_id}", extra={"trace_id": trace_id})
            return []
        
        agency_name = config.agency.name
        target_url = config.target_url
        parser_type = config.parser_type
 
    logger.info(f"Starting crawl for {agency_name} (URL: {target_url}, Parser: {parser_type})", extra={"trace_id": trace_id, "agency_id": config.agency_id})
    
    crawler = GenericCrawler(parser_type=parser_type, delay=3.0)
    from services.metrics_collector import BufferedMetricsCollector
    
    try:
        # クロール時間を測定
        with BufferedMetricsCollector.measure("crawl", "duration_ms", labels={"agency_id": config.agency_id}, trace_id=trace_id):
            results: List[CrawlResult] = await crawler.crawl_site(target_url, agency_name=agency_name)
        
        # 抽出された各リンクについて、DB重複チェックを行い、新着ならダウンロードタスクをエンキュー
        enqueued_count = 0
        with get_db() as session:
            pdf_repo = PDFRepository(session)
            
            for res in results:
                # すでに同じURLで処理されたドキュメントがあるかチェック
                if pdf_repo.exists_by_url(res.url):
                    logger.debug(f"URL already processed, skipping: {res.url}")
                    continue
                
                # 新着PDFリンクなので、ダウンロードタスクをRedisキューへ登録 (非同期実行)
                download_queue.enqueue(
                    download_pdf_task,
                    config.agency_id,
                    res.title,
                    res.url,
                    res.publish_date,
                    job_timeout=120,
                    result_ttl=86400
                )
                enqueued_count += 1
                
        logger.info(f"Crawl completed. Found {len(results)} links, enqueued {enqueued_count} new downloads.")
        
        BufferedMetricsCollector.record("crawl", "success", 1.0, labels={"agency_id": config.agency_id}, trace_id=trace_id)
        BufferedMetricsCollector.record("crawl", "links_found", float(len(results)), labels={"agency_id": config.agency_id}, trace_id=trace_id)
        BufferedMetricsCollector.record("crawl", "links_enqueued", float(enqueued_count), labels={"agency_id": config.agency_id}, trace_id=trace_id)
        BufferedMetricsCollector.flush()

        # ログ用にシリアライズ可能な辞書形式にして返す
        return [{"title": r.title, "url": r.url, "publish_date": r.publish_date} for r in results]
        
    except Exception as e:
        logger.error(f"Error during crawl of config {crawl_config_id}: {e}", exc_info=True)
        BufferedMetricsCollector.record("crawl", "success", 0.0, labels={"agency_id": config.agency_id, "error": str(type(e).__name__)}, trace_id=trace_id)
        BufferedMetricsCollector.flush()
        return []


def crawl_agency_task(crawl_config_id: int):
    """
    同期ラッパー。RQワーカーから呼び出されるクロールタスクのエントリポイント。
    """
    import asyncio
    return asyncio.run(crawl_agency_async(crawl_config_id))


# -----------------------------------------------------------------------------
# Pipeline Helpers (Orchestration)
# -----------------------------------------------------------------------------

def trigger_agency_crawl(crawl_config_id: int):
    """
    外部からクロールタスクを起動するためのヘルパー。クロールジョブをRedisキューに登録する。
    """
    crawl_queue.enqueue(crawl_agency_task, crawl_config_id, job_timeout=300, result_ttl=86400)
    logger.info(f"Enqueued crawl task for config ID: {crawl_config_id}")
