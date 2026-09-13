from typing import List, Optional, Dict, Any, Union
from datetime import date
from crawler.base_crawler import BaseCrawler
from crawler.models.crawl_result import CrawlResult
from crawler.parsers.heuristic_parser import HeuristicParser
from crawler.parsers.rss_parser import RSSParser
from crawler.utils.date_parser import parse_date_string, extract_date_from_text
from crawler.utils.date_filter import filter_by_date_range, should_stop_early


class GenericCrawler(BaseCrawler):
    def __init__(
        self,
        parser_type: str = "heuristic",
        delay: float = 5.0,
        timeout: int = 60000,
        max_depth: int = 2,
        categories: Optional[List[str]] = None,
        priority_levels: Optional[List[Union[str, int]]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ):
        # BaseCrawlerに日付範囲・カテゴリ・優先度を渡す
        super().__init__(
            retry=3,
            timeout=timeout // 1000 if timeout > 1000 else timeout,  # ms -> s
            backoff=0.5,
            start_date=start_date,
            end_date=end_date,
            categories=categories,
            priority_levels=priority_levels,
            delay=delay,
        )
        self.parser_type = parser_type
        self.max_depth = max_depth
        self.heuristic_parser = HeuristicParser()
        self.rss_parser = RSSParser()
        self.visited_urls: set = set()

        # 日付範囲（BaseCrawlerでも保持されるが、こちらでも参照用に保持）
        self.start_date = start_date
        self.end_date = end_date

    def extract_item_date(self, item: CrawlResult) -> Optional[date]:
        """CrawlResult から日付を抽出

        優先順位:
        1. announcement_date (公告日)
        2. deadline (締切日)
        3. テキストから抽出
        """
        # announcement_date があれば最優先
        if hasattr(item, "announcement_date") and item.announcement_date:
            if isinstance(item.announcement_date, date):
                return item.announcement_date
            if isinstance(item.announcement_date, str):
                return parse_date_string(item.announcement_date)

        # deadline があれば次点
        if hasattr(item, "deadline") and item.deadline:
            if isinstance(item.deadline, date):
                return item.deadline
            if isinstance(item.deadline, str):
                return parse_date_string(item.deadline)

        # title や snippet から抽出を試みる
        text_parts = []
        if hasattr(item, "title") and item.title:
            text_parts.append(item.title)
        if hasattr(item, "snippet") and item.snippet:
            text_parts.append(item.snippet)

        if text_parts:
            return extract_date_from_text(" ".join(text_parts))

        return None

    async def _extract_links_from_page(self, html: str, base_url: str, agency_name: str, depth: int) -> List[CrawlResult]:
        """
        内部用：指定されたページからリンクを抽出し、depth情報を付与する。
        """
        results = await self.extract_links(html, base_url, agency_name)
        for res in results:
            res.depth = depth
        return results

    def _get_next_depth(self, current_depth: int) -> int:
        """現在のdepthから次のdepthを計算する。"""
        return current_depth + 1

    def _is_depth_within_limit(self, depth: int, max_depth: Optional[int] = None) -> bool:
        """指定されたdepthが制限内であるか判定する。"""
        limit = max_depth if max_depth is not None else self.max_depth
        return depth <= limit

    def _mark_as_visited(self, url: str):
        """URLを訪問済みとしてマークする。"""
        self.visited_urls.add(url)

    def _has_been_visited(self, url: str) -> bool:
        """URLが既に訪問済みか判定する。"""
        return url in self.visited_urls

    def _normalize_url(self, url: str) -> str:
        """URLからフラグメントを除去して正規化する。"""
        return url.split('#')[0].rstrip('/')

    async def extract_links(self, html: str, base_url: str, agency_name: str = "不明") -> List[CrawlResult]:
        results = []
        if self.parser_type == "rss":
            self.logger.info(f"Extracting links using RSS parser for {agency_name}")
            results = self.rss_parser.parse(html, base_url, agency_name)
        elif self.parser_type == "agency_specific":
            self.logger.info(f"Extracting links using Agency Specific Heuristic parser for {agency_name}")
            results = self.heuristic_parser.parse(html, base_url, agency_name)
        elif self.parser_type == "heuristic":
            self.logger.info(f"Extracting links using Heuristic parser for {agency_name}")
            results = self.heuristic_parser.parse(html, base_url, agency_name)
        else:
            self.logger.warning(f"Unknown parser type '{self.parser_type}'. Defaulting to Heuristic parser.")
            results = self.heuristic_parser.parse(html, base_url, agency_name)

        # 抽出結果にカテゴリ情報を付加
        category_info = self.categories[0] if self.categories else None
        for res in results:
            res.category = category_info

        return results

    async def _crawl_single_page(self, page, url: str, agency_name: str, depth: int) -> List[CrawlResult]:
        """
        単一のページをクロールし、抽出されたリンクを返す。
        60秒のタイムアウトを設定。
        """
        import asyncio
        try:
            success = await asyncio.wait_for(
                self.navigate(page, url),
                timeout=60
            )
            if not success:
                self.logger.error(f"Failed to navigate to URL: {url}")
                return []

            html = await page.content()
            return await self._extract_links_from_page(html, page.url, agency_name, depth)
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout occurred while crawling {url}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error during crawl of {url}: {e}", exc_info=True)
            return []

    async def crawl_site(
        self,
        target_url: str,
        agency_name: str = "不明",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[CrawlResult]:
        """
        対象URLを再帰的に巡回し、抽出されたリンクの一覧を返す。
        日付範囲が指定されている場合、範囲外のアイテムをフィルタリングする。

        Args:
            target_url: クロール開始URL
            agency_name: 機関名
            start_date: 開始日（指定時はインスタンス設定を上書き）
            end_date: 終了日（指定時はインスタンス設定を上書き）

        Returns:
            日付範囲内の CrawlResult リスト
        """
        # 引数で指定されていれば一時的に上書き
        original_start = self.start_date
        original_end = self.end_date
        if start_date is not None:
            self.start_date = start_date
        if end_date is not None:
            self.end_date = end_date

        try:
            return await self.crawl_site_recursive(target_url, agency_name)
        finally:
            # 元の設定に戻す
            self.start_date = original_start
            self.end_date = original_end

    async def crawl_site_recursive(self, target_url: str, agency_name: str = "不明") -> List[CrawlResult]:
        """
        指定された深度まで再帰的にサイトをクロールし、入札関連リンクを収集する。
        日付範囲フィルタと早期終了を適用。
        """
        from crawler.parsers.agency_config_loader import AgencyConfigLoader

        config_loader = AgencyConfigLoader()
        config = config_loader.load(agency_name)
        max_depth = config.get("max_depth", self.max_depth)

        self.visited_urls.clear()
        all_results: List[CrawlResult] = []

        # キュー: (url, depth, parent_url)
        queue = [(target_url, 0, None)]

        browser = None
        try:
            browser, context, page = await self.init_browser()

            while queue:
                current_url, depth, parent_url = queue.pop(0)
                normalized_url = self._normalize_url(current_url)

                if self._has_been_visited(normalized_url):
                    continue

                self._mark_as_visited(normalized_url)
                self.logger.info(f"Crawling {normalized_url} at depth {depth}")

                # ページをクロールしてリンクを抽出
                page_results = await self._crawl_single_page(page, normalized_url, agency_name, depth)

                # 日付範囲フィルタ適用
                if self.start_date or self.end_date:
                    filtered_results = filter_by_date_range(
                        page_results,
                        self.start_date,
                        self.end_date,
                        self.extract_item_date,
                    )
                    # フィルタリングされた件数をログ
                    if len(filtered_results) != len(page_results):
                        self.logger.info(
                            f"Date filter: {len(page_results)} -> {len(filtered_results)} items "
                            f"(range: {self.start_date} ~ {self.end_date})"
                        )
                    page_results = filtered_results

                for res in page_results:
                    # parent_url と is_pdf_link の設定
                    res.parent_url = parent_url
                    res.is_pdf_link = (
                        self.heuristic_parser._is_pdf_url(res.url)
                        if hasattr(self.heuristic_parser, "_is_pdf_url")
                        else False
                    )

                    all_results.append(res)

                    # PDFではなく、かつ深度制限内であれば、さらに深くクロールするためにキューに追加
                    if not res.is_pdf_link and self._is_depth_within_limit(depth + 1, max_depth):
                        queue.append((res.url, self._get_next_depth(depth), normalized_url))

                # 早期終了判定: 現在のページの結果がすべて start_date より古い場合
                if self.start_date and should_stop_early(page_results, self.start_date, self.extract_item_date):
                    self.logger.info(f"Early stop at depth {depth}: all items older than {self.start_date}")
                    break

        except Exception as e:
            self.logger.error(f"Recursive crawl error for {target_url}: {e}")
        finally:
            await self.close()

        return all_results