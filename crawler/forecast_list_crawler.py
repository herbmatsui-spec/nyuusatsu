from typing import List, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

from crawler.forecast_base_crawler import ForecastBaseCrawler
from utils.forecast_logger import ForecastLogger


class ForecastListCrawler(ForecastBaseCrawler):
    def __init__(self, delay: float = 3.0, timeout: int = 90000):
        super().__init__(delay=delay, timeout=timeout)
        self.logger = ForecastLogger("ListCrawler")

    async def crawl_forecast_list(self, url: str, agency_name: str = "不明") -> List[Dict[str, Any]]:
        html = await self.fetch_forecast_page(url)
        if not html:
            self.logger.warning(f"No HTML content", url=url)
            return []

        links = await self.extract_forecast_links(html, url)
        self.logger.info(f"Extracted links", url=url, count=len(links), agency=agency_name)
        return links

    async def crawl_with_pagination(self, base_url: str, agency_name: str = "不明") -> List[Dict[str, Any]]:
        all_links = []
        current_url = base_url

        for page_num in range(1, 11):
            self.logger.info(f"Crawling page", page=page_num, url=current_url)

            html = await self.fetch_forecast_page(current_url)
            if not html:
                break

            links = await self.extract_forecast_links(html, base_url)
            if not links:
                break

            all_links.extend(links)

            next_url = self._get_next_page_url(html, base_url, page_num)
            if not next_url or next_url == current_url:
                break

            current_url = next_url

        return self._deduplicate_links(all_links)

    def _get_next_page_url(self, html: str, base_url: str, current_page: int) -> str:
        soup = BeautifulSoup(html, 'html.parser')
        pagination_keywords = ["次へ", "次ページ", "Next", "＞", ">>", "次へ進む", "次のページ"]

        for a_tag in soup.find_all('a', href=True):
            text = a_tag.get_text(strip=True)
            if any(keyword in text for keyword in pagination_keywords):
                href = a_tag['href']
                if href:
                    return urljoin(base_url, href).split('#')[0].rstrip('/')

        return None

    async def extract_table_data(self, html: str) -> List[Dict[str, Any]]:
        results = []
        soup = BeautifulSoup(html, 'html.parser')

        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            headers = []

            for i, row in enumerate(rows):
                cells = row.find_all(['th', 'td'])
                cell_texts = [cell.get_text(strip=True) for cell in cells]

                if i == 0:
                    headers = cell_texts
                else:
                    if len(cell_texts) == len(headers):
                        row_data = dict(zip(headers, cell_texts))
                        results.append(row_data)

        return results

    def parse_budget_amount(self, budget_text: str) -> int:
        if not budget_text:
            return 0

        budget_text = budget_text.replace(',', '').replace('，', '')

        patterns = [
            (r'(\d+(?:\.\d+)?)\s*億円', 100000000),
            (r'(\d+(?:\.\d+)?)\s*万円', 10000),
            (r'(\d+(?:\.\d+)?)\s*円', 1),
        ]

        for pattern, multiplier in patterns:
            match = re.search(pattern, budget_text)
            if match:
                value = float(match.group(1))
                return int(value * multiplier)

        return 0