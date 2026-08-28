"""HTML パーサー実装

- `HtmlParser` は `BaseParser` を継承し、BeautifulSoup で HTML を解析
- 期待フィールド: title, budget, deadline, organization, description など（プロジェクト要件に合わせて拡張可能）
"""

from bs4 import BeautifulSoup
from .base_parser import BaseParser

class HtmlParser(BaseParser):
    def __init__(self, selectors: dict | None = None):
        """selectors: フィールド名 → CSS セレクタ のマッピング。省略時はデフォルトを使用"""
        self.selectors = selectors or {
            "title": "h1.title, h1",
            "organization": "div.org, span.org",
            "budget": "span.budget, div.budget",
            "deadline": "span.deadline, div.deadline",
            "description": "div.description, article",
        }

    def _select_text(self, soup: BeautifulSoup, selector: str) -> str:
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else ""

    def extract_fields(self, raw_text: str) -> dict:
        soup = BeautifulSoup(raw_text, "html.parser")
        result = {}
        for field, selector in self.selectors.items():
            result[field] = self._select_text(soup, selector)
        return result
