import logging
import asyncio
import re
import os
import time
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlsplit

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup
import requests

from crawler.award_base_crawler import AwardBaseCrawler
from config_dir import AppConfig

logger = logging.getLogger(__name__)

class GEPSAwardCrawler(AwardBaseCrawler):
    """
    GEPS (政府電子調達システム) 専用クローラ。
    PDFダウンロードとHTML解析を組み合わせた実装。
    """

    def __init__(self, config: AppConfig):
        super().__init__(config)
        # GEPS固有の設定をAppConfigのCrawlerConfigから取得、またはデフォルト値を使用
        self.sleep_interval = getattr(config.crawler, 'sleep_interval', 1.0)
        self.timeout = getattr(config.crawler, 'timeout', 30000)

    def extract_award_links(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """
        検索結果HTMLから案件一覧を抽出する。
        """
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
                    "url": pdf_url, # AwardBaseCrawlerの期待する形式に合わせる
                    "publish_date": pub_date,
                    "pdf_url": pdf_url
                })
            except Exception as e:
                logger.error(f"Error parsing GEPS row: {e}")
                continue

        return results

    def parse_award_detail(self, html: str) -> Optional[Dict[str, Any]]:
        """
        落札結果詳細HTMLから情報を抽出する。
        注: GEPSの場合、詳細がPDFのみの場合が多いが、HTMLがある場合はここで行う。
        """
        if not html:
            return None
        
        soup = BeautifulSoup(html, "lxml")
        
        # GEPSの落札結果テーブルを解析
        rows = soup.select("table tr")
        if not rows:
            return None
            
        # 最初のデータ行を抽出（ヘッダーを飛ばす想定）
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            
            # 抽出ロジック
            title = cols[0].get_text(strip=True)
            company = cols[1].get_text(strip=True)
            amount_str = cols[2].get_text(strip=True)
            opened_at = cols[3].get_text(strip=True)
            
            return {
                "title": title,
                "company": company,
                "amount": self.safe_extract_amount(amount_str),
                "opened_at": opened_at
            }
            
        return None

    def download_pdf(self, url: str, dest_path: str) -> bool:
        """
        PDFファイルをダウンロードして保存する。
        """
        try:
            time.sleep(self.sleep_interval)
            logger.info(f"Downloading GEPS PDF: {url}")
            
            # 認証やセッションが必要な場合は、ここで適切に処理
            res = requests.get(url, timeout=60, stream=True, headers={"User-Agent": self.config.crawler.user_agent})
            res.raise_for_status()
            
            with open(dest_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"GEPS PDF download failed for {url}: {e}")
            return False

    def _make_filename(self, date_str: str, title: str, url: str) -> str:
        """ファイル名生成（サニタイズ済み）"""
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", title).strip()
        safe_title = safe_title[:60] if safe_title else "untitled"
        date_part = re.sub(r'[\\/:*?"<>|]', "", date_str).strip() if date_str else ""
        if not date_part:
            date_part = os.path.basename(urlsplit(url).path) or "nodate"
        return f"{date_part}_{safe_title}.pdf".replace(" ", "_")[:200]

    async def crawl_geps_with_pdf(self, target_url: str, temp_dir: str, max_pages: int = 1) -> List[Dict[str, Any]]:
        """
        GEPS特有の「一覧からPDFをダウンロードしつつ情報を収集する」フロー。
        """
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)

        all_results = []
        
        # browser, context, page は AwardBaseCrawler.init_browser() で提供されるが、
        # ここでは統合的なフローを実装
        browser, context, page = await self.init_browser()
        try:
            await page.goto(target_url, wait_until="networkidle", timeout=self.timeout)
            
            for page_no in range(1, max_pages + 1):
                html = await page.content()
                items = self.extract_award_links(html, page.url)
                
                for item in items:
                    # PDFダウンロード実行
                    dest_path = os.path.join(temp_dir, self._make_filename(
                        item.get("publish_date", ""), 
                        item.get("title", ""), 
                        item["url"]
                    ))
                    
                    if not os.path.exists(dest_path):
                        self.download_pdf(item["url"], dest_path)
                    
                    all_results.append(item)
                
                # 次ページへの遷移
                next_btn = page.locator("a:has-text('次へ'), a:has-text('次のページ')")
                if await next_btn.count() == 0:
                    break
                await next_btn.first.click()
                await asyncio.sleep(self.sleep_interval)
                await page.wait_for_selector("table", timeout=10000)

        finally:
            await context.close()
            await browser.close()
            
        return all_results
