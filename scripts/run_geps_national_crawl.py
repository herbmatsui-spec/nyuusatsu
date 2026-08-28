import asyncio
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from database.db import get_db
from crawler.geps_crawler_updated import GEPSCrawler
from services.geps_mapping_service import GEPSMappingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_geps_national_crawl():
    """
    GEPSクローラーを実行し、得られた結果を標準化されたAgencyモデルにマッピングしてDBに保存する。
    """
    crawler = GEPSCrawler()
    
    try:
        logger.info("Starting National Ministry crawl via GEPS...")
        # 初期テストとして最大5ページを巡回
        crawl_results = await crawler.crawl_geps(max_pages=5)
        
        if not crawl_results:
            logger.warning("No results found from GEPS crawl.")
            return

        logger.info(f"Found {len(crawl_results)} potential bid documents. Mapping to DB...")
        
        with get_db() as session:
            mapping_service = GEPSMappingService(session)
            processed_count = mapping_service.process_geps_results(crawl_results)
            logger.info(f"Successfully mapped {processed_count} results to agencies.")

    except Exception as e:
        logger.exception(f"Critical error during national crawl: {e}")
    finally:
        # crawler.close() は crawl_geps 内部で呼ばれているが、念のため
        pass

if __name__ == "__main__":
    asyncio.run(run_geps_national_crawl())
