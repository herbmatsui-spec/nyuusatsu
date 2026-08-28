"""
Hokkaido Award Crawler
北海道の落札結果公告を対象とするクローラ実装。
"""
import logging
from typing import Any, Dict, List, Optional

from crawler.award_base_crawler import AwardBaseCrawler
from crawler.generic_award_crawler import GenericAwardCrawler
from crawler.parsers.award_parser import (
    extract_industry_from_text,
    parse_date as parse_award_date,
    parse_date as parse_announcement_date,
    parse_budget_amount,
    parse_contract_amount,
    parse_winner_name,
)
from crawler.utils.text_cleaner import remove_html_tags, normalize_whitespace

logger = logging.getLogger(__name__)


class HokkaidoAwardCrawler(GenericAwardCrawler):
    """
    北海道の落札結果を収集するクローラ。
    GenericAwardCrawlerを継承して実装を共通化する。
    """
    def __init__(self):
        # 北海道のサイト構造に合わせたセレクタ
        # 実際のHTML構造に基づいて調整が必要
        list_selector = "table.result-list tr.item"
        
        detail_selectors = {
            "title": "h1.page-title",
            "amount": ".amount-value",
            "company": ".company-name",
            "date": ".award-date",
            "agency": ".agency-name"
        }
        
        super().__init__(
            agency_key="hokkaido",
            list_selector=list_selector,
            detail_selectors=detail_selectors
        )

    def __repr__(self):
        return f"<{self.__class__.__name__} (agency={self.agency_key})>"

    def crawl(self, limit: int = 20) -> List[Dict[str, Any]]:
        """一覧→詳細の順でクロールし、落札結果のリストを返す。"""
        url = get_award_list_url("hokkaido")
        if not url:
            logger.error("Hokkaido award list URL not found in config")
            return []
        links = self.crawl_award_list(url)
        results: List[Dict[str, Any]] = []
        for link in links[:limit]:
            detail = self.crawl_award_detail(link["url"])
            if detail:
                detail["source_url"] = link["url"]
                results.append(detail)
        return results
