"""クローラ基底クラス

- すべてのカスタムクローラはこのクラスを継承し、共通ロジック（リトライ付き取得等）を利用できる
- `parse_list` と `parse_detail` は子クラスで実装する抽象メソッド
- 日付範囲指定による絞り込み機能を提供
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import List, Any, Optional
from datetime import date, datetime

import requests

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    def __init__(
        self,
        retry: int = 3,
        timeout: int = 15,
        backoff: float = 0.5,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ):
        self.retry = retry
        self.timeout = timeout
        self.backoff = backoff
        self.start_date = start_date
        self.end_date = end_date

    def fetch(self, url: str) -> str:
        """HTTP GET with simple exponential backoff retry"""
        attempt = 0
        while attempt < self.retry:
            try:
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                logger.warning(f"Fetch error {e} for {url}, attempt {attempt + 1}/{self.retry}")
                attempt += 1
                time.sleep(self.backoff * (2 ** attempt))
        raise RuntimeError(f"Failed to fetch {url} after {self.retry} attempts")

    def crawl_range(
        self,
        start_url: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Any]:
        """指定された日付範囲でクロールを実行

        Args:
            start_url: クロール開始URL
            start_date: 開始日（None の場合はインスタンス設定を使用）
            end_date: 終了日（None の場合はインスタンス設定を使用）

        Returns:
            日付範囲内のアイテムリスト
        """
        # 引数で指定されていれば上書き、なければインスタンス設定を使用
        effective_start = start_date or self.start_date
        effective_end = end_date or self.end_date

        if effective_start or effective_end:
            logger.info(f"Date range filter: start={effective_start}, end={effective_end}")

        # 子クラスの crawl_site または同等のメソッドを呼び出し
        # 基底クラスでは parse_list ベースの簡易実装を提供
        all_items = []
        current_url = start_url

        while current_url:
            html = self.fetch(current_url)
            items = self.parse_list(html)

            # 日付フィルタ適用
            filtered_items = self._filter_by_date_range(items, effective_start, effective_end)
            all_items.extend(filtered_items)

            # 次ページURL取得（子クラスで実装）
            current_url = self._get_next_page_url(html, current_url)

            # 早期終了判定: 現在のページで start_date より古いアイテムのみなら打ち切り
            if effective_start and self._should_stop_early(items, effective_start):
                logger.info(f"Early stop: all items older than {effective_start}")
                break

        return all_items

    def _filter_by_date_range(
        self,
        items: List[Any],
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> List[Any]:
        """アイテムリストを日付範囲でフィルタリング

        子クラスでオーバーライドしてアイテムから日付を取得するロジックを実装
        """
        if not start_date and not end_date:
            return items

        from crawler.utils.date_filter import filter_by_date_range

        # アイテムから日付を抽出する関数を子クラスで提供することを期待
        date_extractor = getattr(self, "extract_item_date", None)
        if not date_extractor:
            logger.warning("extract_item_date method not implemented, skipping date filter")
            return items

        return filter_by_date_range(items, start_date, end_date, date_extractor)

    def _should_stop_early(self, items: List[Any], start_date: date) -> bool:
        """現在のページのアイテムがすべて start_date より古いか判定

        ページネーション時の早期終了判定用
        """
        if not items:
            return False

        date_extractor = getattr(self, "extract_item_date", None)
        if not date_extractor:
            return False

        from crawler.utils.date_filter import should_stop_early
        return should_stop_early(items, start_date, date_extractor)

    def _get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """次のページURLを取得（子クラスで実装）"""
        return None

    @abstractmethod
    def parse_list(self, html: str) -> List[Any]:
        """一覧ページから対象リンクやオブジェクトのリストを抽出"""
        pass

    @abstractmethod
    def parse_detail(self, html: str) -> Any:
        """詳細ページから構造化データを抽出"""
        pass

    @abstractmethod
    def save(self, items: List[Any]):
        """抽出したアイテムを永続化（DB保存等）する"""
        pass