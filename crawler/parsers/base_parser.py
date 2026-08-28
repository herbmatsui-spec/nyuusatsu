from abc import ABC, abstractmethod
from typing import List
from crawler.models.crawl_result import CrawlResult

class BaseParser(ABC):
    @abstractmethod
    def parse(self, html: str, base_url: str, agency_name: str) -> List[CrawlResult]:
        """
        HTMLコンテンツを解析し、入札情報・仕様書PDFなどのリンクを抽出して返す。
        """
        pass
