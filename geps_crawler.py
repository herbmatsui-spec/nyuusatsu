"""
GEPS（政府調達ポータル）特化クローラー
- Playwright(asyncio) で動的レンダリング対応
- 検索結果から 案件名 / 発注機関 / PDF仕様書リンク / 公示日 を抽出
- ダウンロードしたPDFを ./temp_pdfs/ に一括保存（既存 bid_processor.py 互換）
- ページ遷移・ダウンロードごとに time.sleep(5) でアクセス制限回避
- try-except 徹底で 1件失敗でも継続
"""
import asyncio
import os
import re
import time
import logging
import argparse
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlsplit

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv

load_dotenv()

# -----------------------------------------------------------------------------
# Configuration & Exceptions
# -----------------------------------------------------------------------------

@dataclass
class CrawlerConfig:
    search_url: str = "https://www.geps.go.jp/index.html"
    temp_dir: str = "./temp_pdfs"
    sleep_interval: int = 5
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    timeout: int = 60000

class CrawlerError(Exception):
    """Crawler related base exception"""
    pass

class BrowserError(CrawlerError):
    """Browser initialization or navigation error"""
    pass

class ParsingError(CrawlerError):
    """HTML parsing error"""
    pass

class DownloadError(CrawlerError):
    """PDF download error"""
    pass

# -----------------------------------------------------------------------------
# GEPSCrawler Class
# -----------------------------------------------------------------------------

class GEPSCrawler:
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session = self._make_session()
        self.pw = None

    def _make_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({"User-Agent": self.config.user_agent})
        return session

    def ensure_temp_dir(self) -> None:
        if not os.path.exists(self.config.temp_dir):
            os.makedirs(self.config.temp_dir, exist_ok=True)
            self.logger.info(f"Created temp directory: {self.config.temp_dir}")

    async def init_browser(self) -> Tuple[Browser, BrowserContext, Page]:
        """headless Chromium を起動し、Context と Page を返す"""
        try:
            self.pw = await async_playwright().start()
            browser = await self.pw.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=self.config.user_agent)
            page = await context.new_page()
            return browser, context, page
        except Exception as e:
            raise BrowserError(f"Failed to initialize browser: {e}")

    async def navigate_and_wait(self, page: Page, url: str) -> None:
        """ページ遷移し、コンテンツが読み込まれるまで待機する"""
        self.logger.info(f"Navigating to: {url}")
        try:
            await page.goto(url, wait_until="networkidle", timeout=self.config.timeout)
        except Exception as e:
            self.logger.warning(f"goto failed ({e}). Retrying with domcontentloaded.")
            await page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout)
        
        try:
            await page.wait_for_selector("table", timeout=10000)
        except Exception:
            self.logger.warning("Timed out waiting for table selector. Proceeding anyway.")
        
        await asyncio.sleep(self.config.sleep_interval)

    async def get_max_pages(self, page: Page) -> int:
        """次へボタンや件数表示から最大ページ数を推定。失敗時は 1 を返す"""
        try:
            html = await page.content()
            soup = BeautifulSoup(html, "lxml")

            page_links = soup.select("a")
            page_nums: List[int] = []
            for a in page_links:
                txt = a.get_text(strip=True)
                if txt.isdigit():
                    page_nums.append(int(txt))
            if page_nums:
                return max(page_nums)

            next_btn = soup.find("a", string=re.compile(r"次へ|次のページ|next", re.I))
            if not next_btn:
                return 1
            return 1
        except Exception as e:
            self.logger.warning(f"get_max_pages failed ({e}). Assuming single page.")
            return 1

    async def goto_next_page(self, page: Page) -> bool:
        """次ページへ遷移試行。成功で True / 不可で False"""
        try:
            next_btn = page.locator("a:has-text('次へ'), a:has-text('次のページ')")
            if await next_btn.count() == 0:
                return False
            await next_btn.first.click()
            await asyncio.sleep(self.config.sleep_interval)
            try:
                await page.wait_for_selector("table", timeout=10000)
            except Exception:
                pass
            return True
        except Exception as e:
            self.logger.warning(f"goto_next_page failed: {e}")
            return False

    def _make_filename(self, date_str: str, title: str, url: str) -> str:
        """ファイル名生成（公示日_案件名、サニタイズ）"""
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", title).strip()
        safe_title = safe_title[:60] if safe_title else "untitled"
        date_part = re.sub(r'[\\/:*?"<>|]', "", date_str).strip() if date_str else ""
        if not date_part:
            date_part = os.path.basename(urlsplit(url).path) or "nodate"
        return f"{date_part}_{safe_title}.pdf".replace(" ", "_")[:200]

    def parse_results(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """検索結果HTMLから案件情報を抽出する"""
        if not html:
            return []
        
        DATE_RE = re.compile(r"(19|20)\d{1,2}[/\-年]\s*\d{1,2}[/\-月]\s*\d{1,2}日?")
        soup = BeautifulSoup(html, "lxml")
        results: List[Dict[str, Any]] = []

        rows = soup.select("table tr")
        for row in rows:
            try:
                cols = row.find_all("td")
                if len(cols) < 3:
                    continue

                title_el = row.find("a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title:
                    continue

                pdf_url: Optional[str] = None
                href = title_el.get("href", "")
                if href and href.lower().endswith(".pdf"):
                    pdf_url = urljoin(base_url, href)
                else:
                    pdf_link = row.find("a", href=lambda x: x and x.lower().endswith(".pdf"))
                    if pdf_link and pdf_link.get("href"):
                        pdf_url = urljoin(base_url, pdf_link["href"])

                if not pdf_url:
                    continue

                agency = cols[1].get_text(strip=True) if len(cols) > 1 else "不明"

                pub_date = "不明"
                for c in cols:
                    txt = c.get_text(strip=True)
                    m = DATE_RE.search(txt)
                    if m:
                        pub_date = m.group(0)
                        break
                if pub_date == "不明" and len(cols) > 2:
                    pub_date = cols[2].get_text(strip=True)

                results.append({
                    "agency": agency,
                    "title": title,
                    "pdf_url": pdf_url,
                    "publish_date": pub_date
                })
            except Exception as e:
                self.logger.error(f"Error parsing row: {e}")
                continue

        return results

    def parse_award_results(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """落札結果ページから落札情報を抽出する"""
        if not html:
            return []
        
        soup = BeautifulSoup(html, "lxml")
        results: List[Dict[str, Any]] = []
        
        # 落札結果ページのテーブル構造に合わせて解析
        rows = soup.select("table tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            
            # 抽出ロジック（実際のHTML構造に合わせて調整が必要）
            title = cols[0].get_text(strip=True)
            company = cols[1].get_text(strip=True)
            amount_str = cols[2].get_text(strip=True)
            opened_at = cols[3].get_text(strip=True)
            
            results.append({
                "title": title,
                "company": company,
                "amount": amount_str,
                "opened_at": opened_at
            })
        return results

    def download_pdf(self, url: str, dest_path: str) -> bool:
        """PDF をダウンロードし保存する"""
        try:
            time.sleep(self.config.sleep_interval)
            self.logger.info(f"Downloading PDF: {url}")
            res = self.session.get(url, timeout=60, stream=True)
            res.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            self.logger.error(f"Download failed for {url}: {e}")
            return False

    def download_all(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        """抽出結果を元に一括取得"""
        total = len(results)
        ok = 0
        skipped = 0
        failed = 0
        
        for i, item in enumerate(results, 1):
            try:
                filename = self._make_filename(
                    item.get("publish_date", ""), 
                    item.get("title", ""), 
                    item["pdf_url"]
                )
                dest_path = os.path.join(self.config.temp_dir, filename)
                
                if os.path.exists(dest_path):
                    self.logger.info(f"[{i}/{total}] Skipping existing: {filename}")
                    skipped += 1
                    continue
                
                if self.download_pdf(item["pdf_url"], dest_path):
                    self.logger.info(f"[{i}/{total}] Saved: {filename}")
                    ok += 1
                else:
                    failed += 1
            except Exception as e:
                self.logger.error(f"[{i}/{total}] Unexpected error on item: {e}")
                failed += 1
        
        self.logger.info(f"Download summary: success={ok} skipped={skipped} failed={failed} total={total}")
        return {"success": ok, "skipped": skipped, "failed": failed}

    async def crawl(self, target_url: str, max_pages: int = 0, is_award: bool = False) -> List[Dict[str, Any]]:
        """メインクロールフロー"""
        self.ensure_temp_dir()
        browser, context, page = await self.init_browser()
        
        try:
            all_results: List[Dict[str, Any]] = []
            await self.navigate_and_wait(page, target_url)
            
            detected_max = await self.get_max_pages(page)
            pages_to_crawl = min(max_pages, detected_max) if max_pages > 0 else detected_max
            self.logger.info(f"Crawling up to {pages_to_crawl} page(s).")

            for page_no in range(1, pages_to_crawl + 1):
                try:
                    self.logger.info(f"--- Parsing page {page_no} ---")
                    html = await page.content()
                    if is_award:
                        items = self.parse_award_results(html, page.url)
                    else:
                        items = self.parse_results(html, page.url)
                    self.logger.info(f"Found {len(items)} items on page {page_no}.")
                    all_results.extend(items)

                    if page_no < pages_to_crawl:
                        if not await self.goto_next_page(page):
                            self.logger.info("No more pages available.")
                            break
                except Exception as e:
                    self.logger.error(f"Error on page {page_no}: {e}")
                    continue

            if not is_award and all_results:
                self.download_all(all_results)
            elif not all_results:
                self.logger.info("No items found.")
            
            return all_results

        finally:
            await context.close()
            await browser.close()
            if self.pw:
                await self.pw.stop()

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("crawler_error.log", encoding="utf-8")
        ]
    )

async def main():
    parser = argparse.ArgumentParser(description="GEPS dedicated crawler")
    parser.add_argument("--url", type=str, default=CrawlerConfig.search_url, help="GEPS search results URL")
    parser.add_argument("--max-pages", type=int, default=0, help="Max pages to crawl (0=auto)")
    args = parser.parse_args()

    setup_logging()
    config = CrawlerConfig(search_url=args.url)
    crawler = GEPSCrawler(config)
    
    try:
        await crawler.crawl(config.search_url, args.max_pages)
    except Exception as e:
        logging.error(f"Critical error during GEPS crawl: {e}")

if __name__ == "__main__":
    asyncio.run(main())
