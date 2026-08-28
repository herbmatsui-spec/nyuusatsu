import asyncio
import logging
import datetime
from typing import List, Tuple
from sqlalchemy.orm import Session
from database.engine import SessionLocal
from services.url_probe_common import probe_all_urls, ProbeResult
from database.repositories import get_active_agency_urls, save_url_probe_log
from services.notification_service import NotificationService
from services.crawl_service import CrawlService

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("logs/url_monitor.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("url_monitor")

async def run_url_monitor():
    """
    全自治体URLの到達性をチェックし、結果をDBに保存し、失敗があれば通知する。
    """
    logger.info("Starting URL monitor task...")
    
    session = SessionLocal()
    # サービスの初期化
    crawl_service = CrawlService(session)
    notification_service = NotificationService(crawl_service)
    try:
        # 1. URLプローブの実行 (並列実行)
        # タイムアウトと並列数は必要に応じて調整
        results = await probe_all_urls(session, timeout=15.0, concurrency=10)
        
        # 2. 自治体情報を再取得して名前とURLを紐付け
        # (probe_all_urlsはProbeResultのみを返すため、DBから名前を引く)
        from database.models.agency import Agency
        agencies = {a.base_url: a.name for a in session.query(Agency).filter(Agency.base_url != None).all()}
        
        failures = []
        
        for result in results:
            agency_name = agencies.get(result.url, "不明な自治体")
            
            if result.is_reachable:
                status = "success"
                error_msg = None
            else:
                status = "failed"
                error_msg = result.error
                failures.append((agency_name, result.url))
            
            # DBにログを保存
            # agency_id を取得して保存
            agency = session.query(Agency).filter(Agency.base_url == result.url).first()
            if agency:
                save_url_probe_log(session, agency.id, status, error_msg)
        
        # 3. 失敗がある場合に通知
        if failures:
            logger.warning(f"Detected {len(failures)} URL failures. Sending notifications...")
            notification_service.notify_url_failures(failures)
        else:
            logger.info("All URLs are reachable.")
            
        logger.info(f"URL monitor task completed. Probed {len(results)} URLs, {len(failures)} failed.")

    except Exception as e:
        logger.exception(f"Unexpected error during URL monitor task: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    try:
        asyncio.run(run_url_monitor())
    except KeyboardInterrupt:
        pass
