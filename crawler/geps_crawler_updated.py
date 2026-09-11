"""
GEPS（政府電子調達システム）特化クローラー
- BaseCrawlerを継承し、共通のブラウザ管理、レートリミット、ロギングを利用
- GEPSの検索結果から案件名 / 発注機関 / PDF仕様書リンク / 公示日 を抽出
"""
import asyncio
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup

from crawler.base_crawler import BaseCrawler
from crawler.models.crawl_result import CrawlResult
from config_dir import AppConfig

class GEPSCrawler(BaseCrawler):
    def __init__(
        self, 
        delay: float = 5.0, 
        timeout: int = 60000, 
        categories: Optional[List[str]] = None, 
        priority_levels: Optional[List[int]] = None
    ):
        super().__init__(delay, timeout, categories, priority_levels)
        self.search_url = "https://www.geps.go.jp/index.html"
        self.temp_dir = "./temp_pdfs"

    def ensure_temp_dir(self) -> None:
        """PDF保存用の一時ディレクトリを確保する"""
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)
            self.logger.info(f"Created temp directory: {self.temp_dir}")

    async def extract_links(self, html: str, base_url: str, agency_name: str = "GEPS") -> List[CrawlResult]:
        """
        GEPSの検索結果ページから入札情報を抽出する。
        """
        results = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # GEPSの検索結果テーブルを解析 (実際の実装に合わせてセレクタを調整)
        # ここでは仮にテーブル行を走査してリンクを抽出するロジックを実装
        rows = soup.find_all('tr')
        for row in rows:
            links = row.find_all('a', href=True)
            for link in links:
                url = urljoin(base_url, link['href'])
                # PDFリンクや詳細ページリンクを抽出
                if 'pdf' in url.lower() or 'detail' in url.lower():
                    results.append(CrawlResult(
                        url=url,
                        title=link.text.strip() or "GEPS Bid Document",
                        agency_name=agency_name,
                        category="National"
                    ))
        
        return results

    async def crawl_geps(self, target_url: str = None, max_pages: int = 1) -> List[CrawlResult]:
        """
        GEPSのメイン巡回フロー。
        """
        url = target_url or self.search_url
        self.ensure_temp_dir()
        
        browser, context, page = await self.init_browser()
        all_results = []
        
        try:
            success = await self.navigate(page, url)
            if not success:
                self.logger.error(f"Failed to navigate to {url}")
                return []

            for page_num in range(1, max_pages + 1):
                self.logger.info(f"Crawling GEPS page {page_num}...")
                content = await page.content()
                results = await self.extract_links(content, url)
                all_results.extend(results)
                
                # 次ページへの遷移ロジック (GEPSの仕様に合わせて実装)
                next_button = page.locator("a:has-text('次へ'), a:has-text('次のページ')")
                if await next_button.count() > 0:
                    await next_button.click()
                    await asyncio.sleep(self.delay)
                    await page.wait_for_load_state("networkidle")
                else:
                    break
                    
        except Exception as e:
            self.logger.exception(f"Error during GEPS crawl: {e}")
        finally:
            await self.close()
            
        return all_results

    async def close(self) -> None:
        """ブラウザリソースの解放"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
