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
            config = yaml.safe_load(f)
            # Ensure detail_fields exists for parsing
            config.setdefault("detail_fields", {})
            return config

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
    def parse_detail(self, html: str) -> Any:
        # If detail_fields is not defined, fallback to raw text extraction
        detail_fields = self.config.get("detail_fields", {})
        if not detail_fields:
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n", strip=True)

        soup = BeautifulSoup(html, "html.parser")
        result = {}

        # Import transform map
        from crawler.parsers.field_normalizer import TRANSFORM_MAP

        for field_name, field_cfg in detail_fields.items():
            selector = field_cfg.get("selector")
            attr = field_cfg.get("attr", "text")
            transform_name = field_cfg.get("transform")
            multiple = field_cfg.get("multiple", False)

            # Get element(s)
            if multiple:
                elements = soup.select(selector)
                element = soup.select_one(selector)
                elements = [element] if element else []

        # If detail_fields is not defined, fallback to raw text extraction
        detail_fields = self.config.get("detail_fields", {})
        if not detail_fields:
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n", strip=True)

        soup = BeautifulSoup(html, "html.parser")
        result = {}

        # Import transform map
        from crawler.parsers.field_normalizer import TRANSFORM_MAP

        for field_name, field_cfg in detail_fields.items():
            selector = field_cfg.get("selector")
            attr = field_cfg.get("attr", "text")
            transform_name = field_cfg.get("transform")
            multiple = field_cfg.get("multiple", False)

            # Get element(s)
            if multiple:
                elements = soup.select(selector)
            else:
                element = soup.select_one(selector)
                elements = [element] if element else []

            # If no element found, skip or set None/empty
            if not elements:
                result[field_name] = None if not multiple else []
                continue

            # Extract values
            values = []
            for el in elements:
                if el is None:
                    continue  # Skip None elements
                if attr == "text":
                    val = el.get_text(strip=True)
                elif attr == "href":
                    val = el.get("href")
                elif attr == "src":
                    val = el.get("src")
                else:
                    # For other attributes, try to get the attribute value
                    val = el.get(attr)
                values.append(val)

            # Apply transform if specified
            if transform_name and transform_name in TRANSFORM_MAP:
                transform_func = TRANSFORM_MAP[transform_name]
                values = [transform_func(v) for v in values]

            # Store result
            if multiple:
                result[field_name] = values
            else:
                # Take first value if exists, else None
                result[field_name] = values[0] if values else None

        return result
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
    def save(self, items: List[dict], repository: "BidRepository | AwardResultRepository"):
        """Save items to the specified repository
        
        Args:
            items: List of dictionaries representing items to save
            repository: Repository object to use for saving (BidRepository or AwardResultRepository)
        """
        # Create objects from items and save them using the repository
        if repository.__class__.__name__ == "BidRepository":
            # For BidRepository, we need to create Bid objects
            for item in items:
                # Create a dictionary with the item data and add any missing fields
                # This is a simplified example - in practice, we would need to map fields properly
                bid_obj = repository._map_to_bid_model(item)
                repository.save_bid(session=repository.get_session(), bid=bid_obj)
        elif repository.__class__.__name__ == "AwardResultRepository":
            # For AwardResultRepository, we need to create AwardResult objects
            for item in items:
                award_result_obj = repository._map_to_award_result_model(item)
                repository.save_award_result(session=repository.get_session(), award_result=award_result_obj)
        else:
            raise ValueError(f"Unsupported repository type: {repository.__class__.__name__}")
