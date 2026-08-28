import logging
from typing import List, Dict, Any, Optional
from crawler.generic_award_crawler import GenericAwardCrawler

class OsakaAwardCrawler(GenericAwardCrawler):
    """
    大阪府の落札結果を収集するクローラ。
    GenericAwardCrawlerを継承し、大阪府のサイト構造に合わせたセレクタを設定する。
    """
    def __init__(self):
        # 大阪府の落札結果一覧ページのセレクタ
        # 注意: 実際のHTML構造に合わせて調整が必要
        list_selector = "table.result-list tr.item" 
        
        # 詳細ページの抽出セレクタ
        detail_selectors = {
            "title": "h1.page-title",
            "amount": ".amount-value",
            "company": ".company-name",
            "date": ".award-date",
            "agency": ".agency-name"
        }
        
        super().__init__(
            agency_key="osaka",
            list_selector=list_selector,
            detail_selectors=detail_selectors
        )

    def __repr__(self):
        return f"<{self.__class__.__name__} (agency={self.agency_key})>"
