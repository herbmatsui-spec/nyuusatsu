import asyncio
from typing import List, Dict, Any

from crawler.forecast_list_crawler import ForecastListCrawler
from crawler.utils.agency_url_templates import get_forecast_url_candidates
from utils.forecast_logger import ForecastLogger


class ForecastParallelCrawler:
    """複数機関を並列にクロールする（同時実行数制限付き）。"""

    def __init__(self, concurrent_limit: int = 5):
        self.concurrent_limit = concurrent_limit
        self.logger = ForecastLogger("ParallelCrawler")
        self.semaphore = asyncio.Semaphore(concurrent_limit)

    async def crawl_agency(self, agency: Dict[str, Any]) -> List[Dict[str, Any]]:
        async with self.semaphore:
            crawler = ForecastListCrawler()
            try:
                candidates = get_forecast_url_candidates(
                    agency.get("base_url", ""), agency.get("type", "municipality")
                )
                items: List[Dict[str, Any]] = []
                for url in candidates:
                    links = await crawler.crawl_forecast_list(url, agency.get("name", "不明"))
                    items.extend(links)
                return items
            except Exception as e:
                self.logger.error(f"Parallel crawl failed", agency=agency.get("name"), error=str(e))
                return []
            finally:
                await crawler.close()

    async def crawl_all(self, agencies: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        tasks = [self.crawl_agency(a) for a in agencies]
        results = await asyncio.gather(*tasks)
        return {a.get("name", f"agency_{i}"): r for i, (a, r) in enumerate(zip(agencies, results))}
