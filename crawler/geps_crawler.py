import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup
from crawler.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class GEPSCrawler(BaseCrawler):
    """政府調達ポータル（GEPS）用クローラー"""
    
    BASE_URL = "https://www.geps.go.jp"
    
    def __init__(self, delay: float = 5.0, timeout: int = 60000):
        super().__init__(retry=3, timeout=timeout, backoff=0.5)
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

    async def search_bids(self, query: str = "", prefecture_code: str = "01") -> List[Dict[str, Any]]:
        """GEPSで検索を実行"""
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
            
            # 検索実行
            search_button = await page.query_selector('button[type="submit"], input[type="submit"]')
            if search_button:
                await search_button.click()
                await page.wait_for_timeout(3000)  # Wait for results
            
            # 結果を解析
            content = await page.content()
            results = self._parse_search_results(content)
            
        except Exception as e:
            logger.error(f"GEPS search failed: {e}")
        finally:
            await self.close()
        
        return results
    
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
                        "source": "geps"
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