import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from crawler.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class AwardBaseCrawler(BaseCrawler):
    """
    落札結果公告に特化したクローラの抽象基底クラス。
    BaseCrawler の Playwright/requests 基盤を継承し、
    落札結果一覧・詳細の取得・パースを責務とする。
    """

    def extract_award_links(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """
        落札結果一覧ページから各落札案件へのリンク一覧を抽出する。
        戻り値例:
            [{"url": "https://...", "title": "案件名", "date": "2024-01-01"}, ...]
        """
        pass

    async def extract_links(self, html: str, base_url: str, agency_name: str = "不明") -> List[Any]:
        """
        BaseCrawler の抽象メソッドをオーバーライド。
        落札結果のリンク抽出処理に委譲する。
        """
        return self.extract_award_links(html, base_url)

    @abstractmethod
    def parse_award_detail(self, html: str) -> Optional[Dict[str, Any]]:
        """
        落札結果詳細ページから必要な情報を抽出する。
        戻り値例:
            {
                "project_name": "...",
                "agency_name": "...",
                "category": "...",
                "budget_amount": 10000000,
                "contract_amount": 9500000,
                "award_rate": 95.0,
                "winner_name": "株式会社○○",
                "winner_count": 5,
                "announcement_date": "2024-01-01",
                "award_date": "2024-01-15",
            }
        抽出できない場合は None を返す。
        """
        pass

    def crawl_award_list(self, url: str) -> List[Dict[str, Any]]:
        # RPS/Rate Limiting: リクエスト前に待機
        if hasattr(self, 'config') and hasattr(self.config, 'crawler'):
            time.sleep(getattr(self.config.crawler, 'sleep_interval', 1.0))
        """
        一覧ページにアクセスし、リンクを抽出して返す。
        既存 BaseCrawler.navigate を利用。
        """
        import asyncio

        async def _do():
            _, context, page = await self.init_browser()
            try:
                success = await self.navigate(page, url)
                if not success:
                    logger.error(f"Failed to navigate to {url}")
                    return []
                html = await page.content()
                return self.extract_award_links(html, url)
            finally:
                await page.close()
                await self.close()

        return asyncio.run(_do())

    def safe_extract_amount(self, text: Optional[str]) -> Optional[int]:
        """
        金額文字列から数値のみを抽出して整数で返す共通補助メソッド。
        例: "1,234,567円" -> 1234567
        """
        if not text:
            return None
        import re
        # 数字とカンマ以外を除去
        cleaned = re.sub(r'[^\d,]', '', text).replace(',', '')
        try:
            return int(cleaned) if cleaned else None
        except ValueError:
            logger.warning(f"Could not parse amount from text: {text}")
            return None

    def crawl_award_detail(self, url: str) -> Optional[Dict[str, Any]]:
        # RPS/Rate Limiting: リクエスト前に待機
        if hasattr(self, 'config') and hasattr(self.config, 'crawler'):
            time.sleep(getattr(self.config.crawler, 'sleep_interval', 1.0))
        """
        詳細ページにアクセスし、落札情報を抽出して返す。
        """
        import asyncio

        async def _do():
            _, context, page = await self.init_browser()
            try:
                success = await self.navigate(page, url)
                if not success:
                    logger.error(f"Failed to navigate to detail {url}")
                    return None
                html = await page.content()
                return self.parse_award_detail(html)
            finally:
                await page.close()
                await self.close()

        return asyncio.run(_do())
