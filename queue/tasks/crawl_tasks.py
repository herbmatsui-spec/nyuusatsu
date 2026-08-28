import logging
from typing import Optional
from database.session import SessionLocal
from services.crawl_scheduler import CrawlScheduler

logger = logging.getLogger(__name__)

def crawl_agency_task(agency_id: int):
    """
    RQワーカーによって実行されるクロールタスク。
    指定された機関のクロールを実行し、結果をDBに保存する。
    """
    logger.info(f"Starting crawl task for agency_id: {agency_id}")
    try:
        # 1. セッションの作成
        with SessionLocal() as db:
            # 2. スケジューラの初期化
            # 注: CrawlScheduler内部でDBセッションを管理している場合は適切に渡す
            scheduler = CrawlScheduler()
            
            # 機関IDから都道府県IDを特定する必要がある場合、ここで解決
            # 本来は CrawlResult を返す run_crawl_for_prefecture のラップ
            # ここでは簡略化して、特定の機関をターゲットにしたクロールロジックを呼び出す
            
            # 現状の CrawlScheduler は都道府県単位のため、
            # 本来は agency_id から prefecture_id を引き、その都道府県をクロールする
            from database.models import BidSource
            source = db.query(BidSource).filter(BidSource.agency_id == agency_id).first()
            
            if not source:
                logger.error(f"No BidSource found for agency_id: {agency_id}")
                return {"status": "error", "message": "Agency not found"}

            # 都道府県単位のクロールを実行
            result = scheduler.run_crawl_for_prefecture(source.prefecture_id)
            
            logger.info(f"Crawl task completed for agency {agency_id}. Found: {result.bids_found}")
            return {
                "status": "success",
                "agency_id": agency_id,
                "bids_found": result.bids_found,
                "bids_new": result.bids_new
            }
    except Exception as e:
        logger.exception(f"Crawl task failed for agency_id {agency_id}: {e}")
        raise e
