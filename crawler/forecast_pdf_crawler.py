import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from crawler.forecast_base_crawler import ForecastBaseCrawler
from crawler.downloaders.forecast_downloader import ForecastDownloader
from crawler.utils.forecast_url_detector import is_pdf_url
from utils.forecast_logger import ForecastLogger


class ForecastPdfCrawler(ForecastBaseCrawler):
    """発注見通しPDFをダウンロードし、テキスト抽出の準備を行うクローラー。"""

    def __init__(self, delay: float = 3.0, timeout: int = 90000):
        super().__init__(delay=delay, timeout=timeout)
        self.logger = ForecastLogger("PdfCrawler")
        self.downloader = ForecastDownloader()

    async def process_pdf(self, url: str, agency_id: int) -> Optional[Dict[str, Any]]:
        self.logger.info(f"Processing forecast PDF", url=url, agency_id=agency_id)
        download_result = await self.downloader.download_pdf(url, agency_id)
        if not download_result:
            self.logger.error(f"PDF download failed", url=url)
            return None
        return {
            "url": url,
            "filepath": download_result["filepath"],
            "filename": download_result["filename"],
            "sha256": download_result["sha256"],
            "extracted_text": None,
            "extracted_items": [],
        }

    async def extract_pdf_links_from_page(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        links = []
        soup = BeautifulSoup(html, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(base_url, href)
            if is_pdf_url(full_url):
                text = a_tag.get_text(strip=True)
                keywords = ["見通し", "予定", "計画", "事業", "予見", "発注"]
                if any(k in text for k in keywords):
                    links.append({"url": full_url, "text": text})
        return links
