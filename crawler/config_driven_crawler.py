"""設定駆動型クローラ

- `BaseCrawler` を継承し、YAML 設定で対象ページ・パーサー情報を取得
- `parse_list` と `parse_detail` は設定に基づく CSS セレクタを使用
"""

import yaml
from pathlib import Path
from typing import List, Any

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from crawler.base_crawler import BaseCrawler

class ConfigDrivenCrawler(BaseCrawler):
    def __init__(self, config_path: str, **kwargs):
        super().__init__(**kwargs)
        self.config = self._load_config(config_path)
        self.list_selector = self.config.get("list_selector")
        self.detail_selector = self.config.get("detail_selector")
        self.pagination_selector = self.config.get("pagination_selector")
        self.base_url = self.config.get("base_url")
        self.page_format = self.config.get("page_format", "html")

    def _load_config(self, path: str) -> dict:
        with open(Path(path), "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def parse_list(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links = []
        if self.list_selector:
            for el in soup.select(self.list_selector):
                href = el.get("href")
                if href:
                    links.append(urljoin(self.base_url, href))
        return links

    def parse_detail(self, html: str) -> Any:
        # Simple placeholder: return raw text
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n", strip=True)

    def save(self, items: List[Any]):
        # Concrete implementation depends on project DB; stub for now
        for item in items:
            # TODO: integrate with repository layer
            print("[SAVE]", item)
