"""クローラ基底クラス

- すべてのカスタムクローラはこのクラスを継承し、共通ロジック（リトライ付き取得等）を利用できる
- `parse_list` と `parse_detail` は子クラスで実装する抽象メソッド
- 日付範囲指定による絞り込み機能を提供
- agency の category_id と priority_level でフィルタリング可能
- レート制限、プロキシ、リトライ（ジッター付きバックオフ）をサポート
"""

import time
import random
import logging
from abc import ABC, abstractmethod
from typing import List, Any, Optional, Union
from datetime import date, datetime

import requests
import random
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup

# Automatic selector detection imports
from crawler.parsers.structure_detector import StructureDetector
# Rate limiting and proxy imports
from crawler.utils.rate_limiter import RateLimiter
from crawler.utils.proxy_manager import ProxyManager
from crawler.parsers.selector_generator import SelectorGenerator
from crawler.parsers.fallback_selector import FallbackSelector
from crawler.parsers.structure_change_detector import StructureChangeDetector
logger = logging.getLogger(__name__)


PRIORITY_LEVEL_MAP = {"高": 0, "中": 1, "低": 2}


class BaseCrawler(ABC):
    def __init__(
        self,
        retry: int = 3,
        timeout: int = 15,
        backoff: float = 0.5,
        backoff_jitter: float = 0.1,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        use_auto_selector: bool = False,
        categories: Optional[List[str]] = None,
        priority_levels: Optional[List[Union[str, int]]] = None,
        delay: float = 0.0,
        # Rate limiting
        rate_limit: Optional[float] = None,
        # Proxy
        proxy: Optional[str] = None,
        proxy_manager: Optional[ProxyManager] = None,
    ):
        """BaseCrawler のコンストラクタ。

        Args:
            retry: リトライ回数
            timeout: HTTP タイムアウト秒数
            backoff: リトライ時のベースバックオフ秒数
            backoff_jitter: バックオフに加えるジッター（秒）。0 の場合はジッターなし。
            start_date: クロール開始日（フィルタリング用）
            end_date: クロール終了日（フィルタリング用）
            use_auto_selector: 自動セレクタ検出機能のフラグ
            categories: フィルタ対象の agency_categories.name リスト。
                          None の場合はすべてのカテゴリが対象。
            priority_levels: フィルタ対象の priority_level リスト。
                             日本語文字（'高'/'中'/'低'）または整数（0/1/2）指定可能。
                             None の場合はすべての優先度が対象。
            delay: クローリング間の遅延秒数
            rate_limit: リクエスト間隔の最小秒数（レート制限）。None の場合は制限なし。
            proxy: 使用するプロキシURL。None の場合は ProxyManager から取得。
            proxy_manager: ProxyManager インスタンス。None の場合は自動作成。
        """
        self.retry = retry
        self.timeout = timeout
        self.backoff = backoff
        self.backoff_jitter = backoff_jitter
        self.start_date = start_date
        self.end_date = end_date
        self.use_auto_selector = use_auto_selector
        # Initialize automatic selector detection components
        self._structure_detector = StructureDetector()
        self._selector_generator = SelectorGenerator()
        self._fallback_selector = FallbackSelector()
        self._change_detector = StructureChangeDetector()
        # カテゴリ・優先度フィルタリング
        self.categories = categories
        self.priority_levels = priority_levels
        self.delay = delay
        self.logger = logging.getLogger(self.__class__.__name__)

        # Rate limiting
        self._rate_limiter = RateLimiter(rate_limit) if rate_limit else None

        # Proxy
        self._proxy = proxy
        self._proxy_manager = proxy_manager or ProxyManager()

    def _resolve_priority_levels(self) -> List[int]:
        """priority_levels 内の日本語文字を整数に変換して返す。

        '高' -> 0, '中' -> 1, '低' -> 2
        整数のままの場合はそのまま返す。
        """
        if not self.priority_levels:
            return []
        resolved: List[int] = []
        for level in self.priority_levels:
            if isinstance(level, str):
                val = PRIORITY_LEVEL_MAP.get(level)
                if val is not None:
                    resolved.append(val)
                else:
                    self.logger.warning(
                        f"Unknown priority level string '{level}'. "
                        f"Valid: {list(PRIORITY_LEVEL_MAP.keys())}"
                    )
            else:
                resolved.append(int(level))
        return resolved

    def _get_target_agencies(self, db: Session) -> List[Any]:
        """データベースからフィルタ条件に一致する agency を取得する。

        self.categories が指定されている場合は agency_categories.name で絞り込み、
        self.priority_levels が指定されている場合は agency.priority_level で絞り込みます。
        どちらも None の場合は全件を返します（デフォルト動作）。

        Args:
            db: SQLAlchemy Session

        Returns:
            フィルタリングされた Agency オブジェクトのリスト
        """
        from database.models import Agency, AgencyCategory

        query = db.query(Agency)

        if self.categories:
            query = query.join(AgencyCategory, Agency.category_id == AgencyCategory.id)
            query = query.filter(AgencyCategory.name.in_(self.categories))

        resolved_levels = self._resolve_priority_levels()
        if resolved_levels:
            query = query.filter(Agency.priority_level.in_(resolved_levels))

        agencies = query.all()

        if self.categories or resolved_levels:
            self.logger.info(
                f"Target agencies filtered "
                f"(categories={self.categories}, priority_levels={self.priority_levels}): "
                f"{len(agencies)} agencies matched"
            )
        else:
            self.logger.info(f"No filters applied, target agencies: {len(agencies)}")

        return agencies

    # 将来的に非同期版も追加予定: async def async_fetch(self, url: str) -> str:
    def fetch(self, url: str) -> str:
        """HTTP GET with exponential backoff retry, rate limiting, and proxy support."""
        import random
        attempt = 0
        while attempt < self.retry:
            try:
                # Rate limiting
                self._rate_limiter.throttle_sync(url)
                # Proxy
                proxy = self._proxy_manager.get_next_proxy()
                proxies = {"http": proxy, "https": proxy} if proxy else None
                resp = requests.get(url, timeout=self.timeout, proxies=proxies)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                logger.warning(f"Fetch error {e} for {url}, attempt {attempt + 1}/{self.retry}")
                attempt += 1
                if attempt < self.retry:
                    # Exponential backoff with jitter
                    jitter = random.uniform(0, self.backoff * attempt)
                    wait_time = self.backoff * (2 ** attempt) + jitter
                    time.sleep(wait_time)
        raise RuntimeError(f"Failed to fetch {url} after {self.retry} attempts")

    def _auto_select_elements(self, html: str, fallback_selectors: Optional[List[str]] = None) -> List:
        """Automatically detect structure and select elements.
        Returns list of BeautifulSoup Tag elements.
        """
        soup = BeautifulSoup(html, 'html.parser')
        # Detect structure
        structure_type = self._structure_detector.detect_structure(soup)
        # Generate selector based on structure
        selector = self._selector_generator.generate_selector(soup, structure_type) if structure_type != 'unknown' else None
        selectors_to_try = []
        if selector:
            selectors_to_try.append(selector)
        if fallback_selectors:
            selectors_to_try.extend(fallback_selectors)
        # If no selectors, return empty list
        if not selectors_to_try:
            return []
        # Try selectors with fallback
        elements = self._fallback_selector.select_with_fallback(soup, selectors_to_try, min_results=1)
        if elements is None:
            return []
        # TODO: Record success for change detection
        return elements

    def record_selector_success(self, selector: str, html: str) -> None:
        """Record a successful selector execution for change detection."""
        soup = BeautifulSoup(html, 'html.parser')
        self._change_detector.record_success(selector, soup)

    def has_selector_changed(self, selector: str, html: str, threshold: float = 0.5) -> bool:
        """Check if the selector results have changed significantly."""
        soup = BeautifulSoup(html, 'html.parser')
        return self._change_detector.has_changed(selector, soup, threshold)

    def auto_select_with_fallback(self, html: str, fallback_selectors: List[str]) -> List:
        """Use automatic structure detection to generate a selector, with fallback selectors.
        Returns list of selected BeautifulSoup elements.
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            # Detect structure
            struct_type = self._structure_detector.detect_structure(soup)
            # Generate selector based on structure
            selector = None
            if struct_type != 'unknown':
                selector = self._selector_generator.generate_selector(soup, struct_type)
            # Prepare selector list: generated selector first, then fallbacks
            selectors_to_try = []
            if selector:
                selectors_to_try.append(selector)
            selectors_to_try.extend(fallback_selectors)
            # Remove duplicates while preserving order
            seen = set()
            unique_selectors = []
            for sel in selectors_to_try:
                if sel not in seen:
                    seen.add(sel)
                    unique_selectors.append(sel)
            # Try selectors with fallback
            elements = self._fallback_selector.select_with_fallback(soup, unique_selectors, min_results=1)
            if elements is None:
                return []
            # Record success for change detection (if we have a selector that worked)
            # For simplicity, record the first selector that succeeded? We'll skip for now.
            return elements
        except Exception as e:
            logger.error(f"Error in auto selector detection: {e}")
            # Fallback to just trying the fallback selectors
            soup = BeautifulSoup(html, 'html.parser')
            return self._fallback_selector.select_with_fallback(soup, fallback_selectors, min_results=1) or []


    # 将来的に非同期版も追加予定: async def async_crawl_range(...)
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
        # TODO: 将来的にここを非同期バージョンに置き換える
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

    async def async_fetch_stub(self, url: str) -> str:
        """将来的に実装される非同期フェッチのスタブ"""
        # TODO: 実際の非同期HTTPクライアント実装
        return await asyncio.sleep(0, result="")  # プレースホルダー


# 非同期機能の非常に基本的なテスト
# 注: BaseCrawlerは抽象クラスなので実際のテストは具体的なサブクラスで行う
if __name__ == "__main__":
    import asyncio
    print("BaseCrawler is an abstract class. Test concrete subclasses for async functionality.")
    # asyncio.run(test_async())  # 現在はコメントアウト
