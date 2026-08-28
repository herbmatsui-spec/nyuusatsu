"""
Award Crawl Task
スケジューラから呼び出される落札結果クロール処理。
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def run_award_crawl(agency_id: Optional[int] = None, limit: int = 50) -> Dict[str, Any]:
    """
    落札結果のクロールを実行する。
    agency_id が指定されていれば該当自治体のみ、なければ全自治体。
    戻り値: {"saved": int, "skipped": int, "failed": int}
    """
    try:
        from crawler.award_list_crawler import AwardListCrawler
        from services.award_pipeline import AwardPipeline

        logger.info("Starting award crawl task...")
        pipeline = AwardPipeline()

        crawler = AwardListCrawler()
        results = crawler.crawl(limit_per_agency=limit)

        saved = 0
        skipped = 0
        failed = 0

        for data in results:
            try:
                obj = pipeline.run(data)
                if obj:
                    saved += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.error(f"Pipeline error for {data}: {e}")
                failed += 1

        result = {"saved": saved, "skipped": skipped, "failed": failed, "total": len(results)}
        logger.info(f"Award crawl complete: {result}")
        return result
    except Exception as e:
        logger.error(f"Award crawl task failed: {e}")
        return {"saved": 0, "skipped": 0, "failed": 0, "total": 0}


def execute_award_crawl():
    """同期ラッパー（crawler_task.py から呼ぶ用）。"""
    return run_award_crawl()
