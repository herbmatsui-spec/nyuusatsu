import asyncio
import logging
import os
from datetime import date, datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup
from crawler.base_crawler import BaseCrawler
from crawler.utils.date_parser import parse_date_string
from crawler.utils.date_filter import filter_by_date_range

logger = logging.getLogger(__name__)


class GEPSCrawler(BaseCrawler):
    """政府調達ポータル（GEPS）用クローラー"""

    BASE_URL = "https://www.geps.go.jp"

    def __init__(
        self,
        delay: float = 5.0,
        timeout: int = 60000,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ):
        super().__init__(
            retry=3,
            timeout=timeout // 1000 if timeout > 1000 else timeout,
            backoff=0.5,
            start_date=start_date,
            end_date=end_date,
        )
        self.delay = delay
        self.timeout = timeout
        self.playwright = None
        self.browser = None
        self.context = None

    async def init_browser(self, headless: bool = True) -> tuple:
        """Playwrightブラウザの初期化"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=headless)
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await self.context.new_page()
            page.set_default_timeout(self.timeout)
            return self.browser, self.context, page
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise

    async def search_bids(
        self,
        query: str = "",
        prefecture_code: str = "01",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """GEPSで検索を実行（日付範囲対応）

        Args:
            query: 検索キーワード
            prefecture_code: 都道府県コード
            start_date: 開始日（公告日基準）
            end_date: 終了日（公告日基準）

        Returns:
            検索結果のリスト
        """
        # 引数で指定されていれば一時的に上書き
        original_start = self.start_date
        original_end = self.end_date
        if start_date is not None:
            self.start_date = start_date
        if end_date is not None:
            self.end_date = end_date

        results = []
        browser = context = page = None
        try:
            browser, context, page = await self.init_browser()
            search_url = f"{self.BASE_URL}/search.html"
            await page.goto(search_url, wait_until="networkidle")

            # 検索フォームに入力
            search_input = await page.query_selector('input[name="query"], input#query, input[type="search"]')
            if search_input:
                await search_input.fill(query)

            # 日付範囲指定（GEPSの検索フォームに日付項目がある場合）
            if self.start_date or self.end_date:
                await self._set_date_range(page)

            # 検索実行
            search_button = await page.query_selector('button[type="submit"], input[type="submit"]')
            if search_button:
                await search_button.click()
                await page.wait_for_timeout(3000)  # Wait for results

            # 結果を解析
            content = await page.content()
            results = self._parse_search_results(content)

            # 日付範囲でフィルタリング（サイト側でフィルタできない場合のフォールバック）
            if self.start_date or self.end_date:
                filtered = filter_by_date_range(
                    results,
                    self.start_date,
                    self.end_date,
                    self._extract_item_date,
                )
                if len(filtered) != len(results):
                    logger.info(f"GEPS date filter: {len(results)} -> {len(filtered)} items")
                results = filtered

        except Exception as e:
            logger.error(f"GEPS search failed: {e}")
        finally:
            await self.close()
            # 元の設定に戻す
            self.start_date = original_start
            self.end_date = original_end

        return results

    async def _set_date_range(self, page: Page):
        """GEPS検索フォームの日付項目に値を設定"""
        try:
            # 一般的な日付入力フィールドのセレクタ
            date_selectors = {
                "start": [
                    'input[name="startDate"], input[name="fromDate"], input[name="dateFrom"]',
                    'input[id*="start"], input[id*="from"]',
                    'input[placeholder*="開始"], input[placeholder*="から"]',
                ],
                "end": [
                    'input[name="endDate"], input[name="toDate"], input[name="dateTo"]',
                    'input[id*="end"], input[id*="to"]',
                    'input[placeholder*="終了"], input[placeholder*="まで"]',
                ],
            }

            if self.start_date:
                for selector in date_selectors["start"]:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.fill(self.start_date.strftime("%Y/%m/%d"))
                        logger.debug(f"Set start date: {self.start_date}")
                        break

            if self.end_date:
                for selector in date_selectors["end"]:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.fill(self.end_date.strftime("%Y/%m/%d"))
                        logger.debug(f"Set end date: {self.end_date}")
                        break

        except Exception as e:
            logger.warning(f"Failed to set date range on GEPS form: {e}")

    def _extract_item_date(self, item: Dict[str, Any]) -> Optional[date]:
        """検索結果アイテムから日付を抽出

        優先順位:
        1. announcement_date (公告日) - 詳細ページで取得済みの場合
        2. deadline (締切日)
        3. title/snippet から抽出
        """
        # announcement_date があれば最優先
        if "announcement_date" in item and item["announcement_date"]:
            d = parse_date_string(str(item["announcement_date"]))
            if d:
                return d

        # deadline があれば次点
        if "deadline" in item and item["deadline"]:
            d = parse_date_string(str(item["deadline"]))
            if d:
                return d

        # title から抽出を試みる
        if "title" in item and item["title"]:
            d = parse_date_string(item["title"])
            if d:
                return d

        return None

    def _parse_search_results(self, html: str) -> List[Dict[str, Any]]:
        """検索結果HTMLを解析して構造化データを抽出"""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # GEPSの検索結果ページ構造に基づくパーサー
        for item in soup.find_all('div', class_='search-result-item') or soup.find_all('tr'):
            try:
                title_elem = item.find('a', class_='title') or item.find('td', class_='title')
                org_elem = item.find('span', class_='organization') or item.find('td', class_='organization')
                budget_elem = item.find('span', class_='budget') or item.find('td', class_='budget')
                deadline_elem = item.find('span', class_='deadline') or item.find('td', class_='deadline')

                title = title_elem.get_text(strip=True) if title_elem else "Unknown"
                org = org_elem.get_text(strip=True) if org_elem else "Unknown"
                budget = budget_elem.get_text(strip=True) if budget_elem else ""
                deadline = deadline_elem.get_text(strip=True) if deadline_elem else ""

                link = title_elem.get('href') if title_elem else ""
                full_url = urljoin(self.BASE_URL, link) if link else ""

                if title and full_url:
                    results.append({
                        "title": title,
                        "organization": org,
                        "budget": budget,
                        "deadline": deadline,
                        "url": full_url,
                        "source": "geps",
                    })
            except Exception as e:
                logger.warning(f"Failed to parse item: {e}")

        return results

    async def fetch_pdf_links(self, detail_url: str) -> List[str]:
        """詳細ページからPDFリンクを抽出"""
        pdf_links = []
        browser = context = page = None
        try:
            browser, context, page = await self.init_browser()
            await page.goto(detail_url, wait_until="networkidle")
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.lower().endswith('.pdf'):
                    full_url = urljoin(detail_url, href)
                    pdf_links.append(full_url)
        except Exception as e:
            logger.error(f"Failed to fetch PDF links from {detail_url}: {e}")
        finally:
            await self.close()

        return pdf_links

    async def close(self):
        """リソースのクリーンアップ"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")