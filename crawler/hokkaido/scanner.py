"""北海道庁入札情報クローラー。

- parse(html, base_url): 静的HTMLから案件リンクを抽出（オフライン検証用）。
- crawl(url): Playwright で実際にページを取得してから parse する（本番用）。
"""
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from crawler.base_crawler import BaseCrawler


class HokkaidoCrawler(BaseCrawler):
    def __init__(self, delay: float = 5.0, timeout: int = 60000):
        super().__init__(delay=delay, timeout=timeout)

    @staticmethod
    def parse(html: str, base_url: str) -> List[Dict[str, Any]]:
        """HTML文字列から北海道の入札案件リンクを抽出する。"""
        soup = BeautifulSoup(html, "html.parser")
        results: List[Dict[str, Any]] = []
        seen: set[str] = set()

        keywords = ["入札", "公告", "調達", "仕様書", "指名"]

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            text = link.get_text(strip=True)
            if not href or not text:
                continue
            if not any(k in text for k in keywords):
                continue
            if href.lower().endswith((".pdf", ".xls", ".xlsx")):
                continue  # PDF等は詳細ページで扱う

            full_url = urljoin(base_url, href) if not href.startswith("http") else href
            if full_url in seen:
                continue
            seen.add(full_url)
            results.append({
                "title": text[:200],
                "url": full_url,
                "base_url": base_url,
                "text": text[:500],
            })

        return results

    async def extract_links(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """BaseCrawlerの抽象メソッドを実装。parse()に委譲する。"""
        return self.parse(html, base_url)

    async def crawl(self, url: str) -> List[Dict[str, Any]]:
        """Playwright で実際のページを取得して抽出する。"""
        browser = None
        try:
            browser, context, page = await self.init_browser()
            ok = await self.navigate(page, url)
            if not ok:
                return []
            html = await page.content()
            return self.parse(html, page.url)
        finally:
            await self.close()
