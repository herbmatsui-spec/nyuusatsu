"""
Award List Crawler
複数自治体の落札結果一覧を巡回し、詳細情報を取得する。
"""
import logging
from typing import Any, Dict, List, Optional

from crawler.award_base_crawler import AwardBaseCrawler
from crawler.hokkaido.award_crawler import HokkaidoAwardCrawler
from crawler.tokyo.award_crawler import TokyoAwardCrawler
from crawler.osaka.award_crawler import OsakaAwardCrawler
from crawler.geps.award_crawler import GEPSAwardCrawler
from config.award_urls import AWARD_URL_PATTERNS

logger = logging.getLogger(__name__)


CRAWLER_MAP = {
    "hokkaido": HokkaidoAwardCrawler,
    "tokyo": TokyoAwardCrawler,
    "osaka": OsakaAwardCrawler,
    "geps": GEPSAwardCrawler,
}


def get_crawler_for_agency(agency_key: str) -> Optional[AwardBaseCrawler]:
    """自治体キーに対応するクローラインスタンスを返す。"""
    crawler_cls = CRAWLER_MAP.get(agency_key)
    if crawler_cls:
        # GEPSAwardCrawlerなどの一部のクローラはAppConfigを必要とするため
        # ここでインスタンス化の仕方を調整する
        from config import AppConfig
        config = AppConfig()
        
        if crawler_cls == GEPSAwardCrawler:
            return crawler_cls(config)
        return crawler_cls()
    return None


class AwardListCrawler:
    """
    複数自治体の落札結果を一括でクロールする。
    未実装の自治体はスキップする。
    """

    def __init__(self, agency_keys: Optional[List[str]] = None):
        if agency_keys is None:
            agency_keys = list(AWARD_URL_PATTERNS.keys())
        self.agency_keys = agency_keys

    def crawl(self, limit_per_agency: int = 20) -> List[Dict[str, Any]]:
        """全自治体の落札結果を取得して結合リストを返す。"""
        all_results: List[Dict[str, Any]] = []
        for key in self.agency_keys:
            crawler = get_crawler_for_agency(key)
            if crawler is None:
                logger.info(f"No crawler for agency: {key} (skipped)")
                continue
            try:
                results = crawler.crawl(limit=limit_per_agency)
                for r in results:
                    r["agency_key"] = key
                all_results.extend(results)
                logger.info(f"Agency {key}: {len(results)} results")
            except Exception as e:
                logger.error(f"Crawl failed for {key}: {e}")
        return all_results
