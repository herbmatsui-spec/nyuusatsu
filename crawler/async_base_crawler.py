"""非同期対応のクローラ基底クラス (Step 29)。

- BaseCrawler の非同期版
- aiohttp を使用した非同期 HTTP 取得
- リトライ・レート制限・プロキシサポートを統合
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import List, Any, Optional, Union
from datetime import date, datetime
from urllib.parse import urlparse

import aiohttp
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup

from crawler.parsers.structure_detector import StructureDetector
from crawler.parsers.selector_generator import SelectorGenerator
from crawler.parsers.fallback_selector import FallbackSelector
from crawler.parsers.structure_change_detector import StructureChangeDetector
from crawler.utils.rate_limiter import RateLimiter
from crawler.utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

PRIORITY_LEVEL_MAP = {"高": 0, "中": 1, "低": 2}


class AsyncBaseCrawler(ABC):
    """非同期クローラ基底クラス。

    同期版 BaseCrawler と互換性のあるインターフェースを提供しつつ、
    aiohttp による非同期 HTTP 取得、レート制限、プロキシサポートを実装。
    """

    def __init__(
        self,
        retry: int = 3,
        timeout: int = 15,
        backoff: float = 0.5,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        use_auto_selector: bool = False,
        categories: Optional[List[str]] = None,
        priority_levels: Optional[List[Union[str, int]]] = None,
        delay: float = 0.0,
        rate_limit: float = 3.0,
        proxies: Optional[List[str]] = None,
    ):
        """AsyncBaseCrawler のコンストラクタ。

        Args:
            retry: リトライ回数
            timeout: HTTP タイムアウト秒数
            backoff: リトライ時のベースバックオフ秒数
            start_date: クロール開始日（フィルタリング用）
            end_date: クロール終了日（フィルタリング用）
            use_auto_selector: 自動セレクタ検出機能のフラグ
            categories: フィルタ対象の agency_categories.name リスト
            priority_levels: フィルタ対象の priority_level リスト
            delay: クローリング間の遅延秒数
            rate_limit: 同一ドメインへの最小アクセス間隔（秒）
            proxies: プロキシURLリスト（None の場合は環境変数 PROXY_LIST から読み込み）
        """
        self.retry = retry
        self.timeout = timeout
        self.backoff = backoff
        self.start_date = start_date
        self.end_date = end_date
        self.use_auto_selector = use_auto_selector
        self._structure_detector = StructureDetector()
        self._selector_generator = SelectorGenerator()
        self._fallback_selector = FallbackSelector()
        self._change_detector = StructureChangeDetector()
        self.categories = categories
        self.priority_levels = priority_levels
        self.delay = delay
        self.logger = logging.getLogger(self.__class__.__name__)

        # 非同期コンポーネント
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = RateLimiter(default_delay=rate_limit)
        self._proxy_manager = ProxyManager(proxies)

    def _resolve_priority_levels(self) -> List[int]:
        """priority_levels 内の日本語文字を整数に変換して返す。"""
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
        """データベースからフィルタ条件に一致する agency を取得する。"""
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

    async def _get_session(self) -> aiohttp.ClientSession:
        """aiohttp セッションを取得または作成する。"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=100)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session

    async def close(self):
        """セッションを閉じる。"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def fetch(
        self,
        url: str,
        headers: Optional[dict] = None,
        proxy: Optional[str] = None,
    ) -> str:
        """非同期 HTTP GET with exponential backoff retry。

        Args:
            url: 取得対象URL
            headers: 追加ヘッダー
            proxy: プロキシURL（指定時はローテーションをスキップ）

        Returns:
            レスポンスボディ（テキスト）
        """
        session = await self._get_session()
        effective_proxy = proxy or self._proxy_manager.get_next_proxy()

        # レート制限
        await self._rate_limiter.throttle(url)

        attempt = 0
        while attempt < self.retry:
            try:
                async with session.get(
                    url,
                    headers=headers or {},
                    proxy=effective_proxy,
                ) as resp:
                    resp.raise_for_status()
                    return await resp.text()
            except asyncio.TimeoutError as e:
                self.logger.warning(f"Fetch timeout {url}: {e}, attempt {attempt + 1}/{self.retry}")
            except aiohttp.ClientError as e:
                self.logger.warning(f"Fetch client error {url}: {e}, attempt {attempt + 1}/{self.retry}")
            except Exception as e:
                self.logger.warning(f"Fetch error {url}: {e}, attempt {attempt + 1}/{self.retry}")

            attempt += 1
            if attempt < self.retry:
                # ジッター付き指数バックオフ
                jitter = 0.1 * (attempt * 0.5)
                wait_time = self.backoff * (2 ** attempt) + jitter
                self.logger.debug(f"Waiting {wait_time:.2f}s before retry")
                await asyncio.sleep(wait_time)

        raise RuntimeError(f"Failed to fetch {url} after {self.retry} attempts")

    async def fetch_with_delay(self, url: str, headers: Optional[dict] = None) -> str:
        """クローリング間の遅延を適用して取得する。"""
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        return await self.fetch(url, headers)

    async def async_crawl_range(
        self,
        start_url: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Any]:
        """指定された日付範囲で非同期クロールを実行。

        Args:
            start_url: クロール開始URL
            start_date: 開始日（None の場合はインスタンス設定を使用）
            end_date: 終了日（None の場合はインスタンス設定を使用）

        Returns:
            日付範囲内のアイテムリスト
        """
        effective_start = start_date or self.start_date
        effective_end = end_date or self.end_date

        if effective_start or effective_end:
            self.logger.info(f"Date range filter: start={effective_start}, end={effective_end}")

        html = await self.fetch_with_delay(start_url)
        return self.parse_list(html)

    @abstractmethod
    def parse_list(self, html: str) -> List[Any]:
        """一覧ページの HTML からアイテムリストを抽出する。

        子クラスで実装必須。

        Args:
            html: 一覧ページの HTML

        Returns:
            アイテムの辞書リスト
        """
        pass

    @abstractmethod
    def parse_detail(self, html: str, item: dict) -> dict:
        """詳細ページの HTML から詳細情報を抽出する。

        子クラスで実装必須。

        Args:
            html: 詳細ページの HTML
            item: parse_list で得られたアイテム

        Returns:
            詳細情報を含む辞書
        """
        pass

    # 以下、自動セレクタ関連メソッド（同期版と同等）
    def _auto_select_elements(self, html: str, fallback_selectors: Optional[List[str]] = None) -> List:
        soup = BeautifulSoup(html, "html.parser")
        structure_type = self._structure_detector.detect_structure(soup)
        selector = self._selector_generator.generate_selector(soup, structure_type) if structure_type != "unknown" else None
        selectors_to_try = []
        if selector:
            selectors_to_try.append(selector)
        if fallback_selectors:
            selectors_to_try.extend(fallback_selectors)
        if not selectors_to_try:
            return []
        elements = self._fallback_selector.select_with_fallback(soup, selectors_to_try, min_results=1)
        return elements or []

    def record_selector_success(self, selector: str, html: str) -> None:
        soup = BeautifulSoup(html, "html.parser")
        self._change_detector.record_success(selector, soup)

    def has_selector_changed(self, selector: str, html: str, threshold: float = 0.5) -> bool:
        soup = BeautifulSoup(html, "html.parser")
        return self._change_detector.has_changed(selector, soup, threshold)

    def auto_select_with_fallback(self, html: str, fallback_selectors: List[str]) -> List:
        try:
            soup = BeautifulSoup(html, "html.parser")
            struct_type = self._structure_detector.detect_structure(soup)
            selector = None
            if struct_type != "unknown":
                selector = self._selector_generator.generate_selector(soup, struct_type)
            selectors_to_try = []
            if selector:
                selectors_to_try.append(selector)
            selectors_to_try.extend(fallback_selectors)
            seen = set()
            unique_selectors = []
            for sel in selectors_to_try:
                if sel not in seen:
                    seen.add(sel)
                    unique_selectors.append(sel)
            elements = self._fallback_selector.select_with_fallback(soup, unique_selectors, min_results=1)
            return elements or []
        except Exception as e:
            self.logger.error(f"Error in auto selector detection: {e}")
            soup = BeautifulSoup(html, "html.parser")
            return self._fallback_selector.select_with_fallback(soup, fallback_selectors, min_results=1) or []


# 既存の BaseCrawler との互換性のためのエイリアス
BaseCrawler = AsyncBaseCrawler