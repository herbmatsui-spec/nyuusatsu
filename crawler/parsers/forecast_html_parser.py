from typing import List, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from crawler.parsers.base_parser import BaseParser
from utils.forecast_logger import ForecastLogger


class ForecastHtmlParser(BaseParser):
    """発注見通し一覧ページ（HTML）を解析し、表データ・リンクを抽出する。"""

    def __init__(self):
        self.logger = ForecastLogger("HtmlParser")

    def parse(self, html: str, base_url: str, agency_name: str = "不明") -> List[Dict[str, Any]]:
        return self.extract_tables(html, base_url)

    def extract_tables(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        results: List[Dict[str, Any]] = []
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            headers: List[str] = []
            for i, row in enumerate(rows):
                cells = row.find_all(["th", "td"])
                cell_texts = [c.get_text(strip=True) for c in cells]
                if i == 0:
                    headers = cell_texts
                elif len(cell_texts) == len(headers):
                    row_data = dict(zip(headers, cell_texts))
                    links = []
                    for a in row.find_all("a", href=True):
                        links.append(urljoin(base_url, a["href"]))
                    row_data["_links"] = links
                    results.append(row_data)
        return results

    def extract_links(self, html: str, base_url: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        links: List[Dict[str, str]] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            links.append({"url": urljoin(base_url, href), "text": text})
        return links
