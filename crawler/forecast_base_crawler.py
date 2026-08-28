import asyncio
import logging
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from crawler.base_crawler import BaseCrawler
from crawler.utils.user_agent import get_random_user_agent
from crawler.utils.proxy_manager import ProxyManager
from crawler.utils.rate_limiter import RateLimiter
from config import AppConfig
from utils.forecast_logger import ForecastLogger


class ForecastBaseCrawler(BaseCrawler):
    def __init__(
        self,
        delay: float = 3.0,
        timeout: int = 90000,
        categories: Optional[List[str]] = None,
        priority_levels: Optional[List[int]] = None
    ):
        super().__init__(delay=delay, timeout=timeout, categories=categories, priority_levels=priority_levels)
        self.logger = ForecastLogger("BaseCrawler")

    async def init_browser(self, headless: bool = True) -> tuple:
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)
        user_agent = get_random_user_agent()
        proxy_config = self.proxy_manager.get_playwright_proxy_dict()
        self.context = await self.browser.new_context(
            user_agent=user_agent,
            proxy=proxy_config,
            ignore_https_errors=True
        )
        return self.browser, self.context

    async def fetch_forecast_page(self, url: str, wait_until: str = "networkidle") -> Optional[str]:
        if not self.browser or not self.context:
            await self.init_browser()

        page = await self.context.new_page()
        try:
            await self.rate_limiter.throttle(url, custom_delay=self.delay)
            await page.goto(url, wait_until=wait_until, timeout=self.timeout)
            await page.wait_for_selector("body", timeout=10000)
            content = await page.content()
            return content
        except Exception as e:
            self.logger.error(f"Failed to fetch forecast page", url=url, error=str(e))
            return None
        finally:
            await page.close()

    async def extract_forecast_links(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        links = []
        soup = BeautifulSoup(html, 'html.parser')

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(base_url, href)
            text = a_tag.get_text(strip=True) or ""

            if self._is_likely_forecast_link(text, full_url):
                links.append({
                    'url': full_url,
                    'text': text,
                    'type': 'forecast'
                })

        return self._deduplicate_links(links)

    async def extract_links(self, html: str, base_url: str, agency_name: str = "不明") -> List[Dict[str, Any]]:
        """BaseCrawlerの抽象メソッドを実装（発注見通し抽出へ委譲）。"""
        return await self.extract_forecast_links(html, base_url)

    def _is_likely_forecast_link(self, text: str, url: str) -> bool:
        forecast_keywords = [
            '発注', '見通し', '予定', '計画', '事業', '工事', '調達',
            'forecast', 'procurement', 'plan'
        ]
        text_lower = text.lower()
        url_lower = url.lower()

        for keyword in forecast_keywords:
            if keyword in text_lower or keyword in url_lower:
                return True
        return False

    def _deduplicate_links(self, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        unique = []
        for link in links:
            normalized = link['url'].split('#')[0].rstrip('/')
            if normalized not in seen:
                seen.add(normalized)
                unique.append(link)
        return unique

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.context = None
        self.browser = None
        self.playwright = None