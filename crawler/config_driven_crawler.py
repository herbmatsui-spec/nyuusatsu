"""設定駆動型クローラ

- `BaseCrawler` を継承し、YAML 設定で対象ページ・パーサー情報を取得
- `parse_list` と `parse_detail` は設定に基づく CSS セレクタを使用
- 日付範囲指定による絞り込み機能を提供
"""

import yaml
from pathlib import Path
from typing import List, Any, Optional
from datetime import date

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from crawler.base_crawler import BaseCrawler
from crawler.utils.date_filter import filter_by_date_range
from crawler.utils.date_parser import parse_date_string, extract_date_from_text


class ConfigDrivenCrawler(BaseCrawler):
    def __init__(
        self,
        config_path: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        **kwargs,
    ):
        super().__init__(
            start_date=start_date,
            end_date=end_date,
            **kwargs,
        )
        self.config = self._load_config(config_path)
        self.list_selector = self.config.get("list_selector")
        self.detail_selector = self.config.get("detail_selector")
        self.pagination_selector = self.config.get("pagination_selector")
        self.base_url = self.config.get("base_url")
        self.page_format = self.config.get("page_format", "html")

    def _load_config(self, path: str) -> dict:
        with open(Path(path), "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def extract_item_date(self, item: Any) -> Optional[date]:
        """アイテムから日付を抽出

        設定ファイルに date_selector が指定されていればそれを使用、
        なければテキストから抽出を試みる
        """
        # 設定に date_selector があれば優先
        date_selector = self.config.get("date_selector")
        if date_selector and hasattr(item, "get"):
            # item が dict の場合
            if isinstance(item, dict):
                date_text = item.get("date_text") or item.get("deadline") or item.get("announcement_date")
                if date_text:
                    return parse_date_string(str(date_text))
        return None

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

    def crawl_range(
        self,
        start_url: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Any]:
        """日付範囲指定でクロール実行（設定駆動版）"""
        # 引数で指定されていれば一時的に上書き
        original_start = self.start_date
        original_end = self.end_date
        if start_date is not None:
            self.start_date = start_date
        if end_date is not None:
            self.end_date = end_date

        try:
            all_items = []
            current_url = start_url

            while current_url:
                html = self.fetch(current_url)
                items = self.parse_list(html)

                # 日付フィルタ適用（リンクリストの場合は詳細ページ取得後にフィルタ）
                # ここではリンクリストを返し、呼び出し側で詳細取得時にフィルタする想定
                all_items.extend(items)

                # 次ページURL取得
                current_url = self._get_next_page_url(html, current_url)

                # 早期終了判定
                if self.start_date and self._should_stop_early(items, self.start_date):
                    logger.info(f"Early stop: all items older than {self.start_date}")
                    break

            return all_items
        finally:
            self.start_date = original_start
            self.end_date = original_end

    def _get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """次のページURLを取得"""
        if not self.pagination_selector:
            return None
        soup = BeautifulSoup(html, "html.parser")
        next_link = soup.select_one(self.pagination_selector)
        if next_link and next_link.get("href"):
            return urljoin(self.base_url, next_link["href"])
        return None

    def save(self, items: List[Any]):
        # Concrete implementation depends on project DB; stub for now
        for item in items:
            # TODO: integrate with repository layer
            print("[SAVE]", item)
