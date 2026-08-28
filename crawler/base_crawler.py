import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from crawler.utils.user_agent import get_random_user_agent
from crawler.utils.proxy_manager import ProxyManager
from crawler.utils.rate_limiter import RateLimiter
from config import AppConfig

class BaseCrawler(ABC):
    def __init__(
        self,
        delay: float = 5.0,
        timeout: int = 60000,
        categories: Optional[List[str]] = None,
        priority_levels: Optional[List[int]] = None
    ):
        """
        クローラーの共通抽象基底クラス。
        Playwrightとrequestsのハイブリッドフォールバックをサポート。
        """
        self.delay = delay
        self.timeout = timeout
        
        # ロガーの統一化: クラス名に基づいた階層的なロガーを設定
        self.logger = logging.getLogger(f"crawler.{self.__class__.__name__}")
        self.logger.setLevel(logging.INFO)
        
        self.rate_limiter = RateLimiter(default_delay=delay)
        self.proxy_manager = ProxyManager()
        self.config = AppConfig()
        self.categories = categories
        self.priority_levels = priority_levels
        
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        
        # Note: http_client and hybrid_client are removed or moved to a different module
        self.http_client = None
        self.hybrid_client = None

    async def init_browser(self, headless: bool = True) -> Tuple[Browser, BrowserContext, Page]:
        """
        Playwrightのブラウザを初期化し、contextと最初のpageを作成する。
        """
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=headless)
            
            # ランダムなUser-Agentの設定
            user_agent = get_random_user_agent()
            
            # プロキシの設定
            proxy_config = self.proxy_manager.get_playwright_proxy_dict()
            
            self.logger.info(f"Launching browser with UA: {user_agent}, Proxy: {proxy_config}")
            self.context = await self.browser.new_context(
                user_agent=user_agent,
                proxy=proxy_config,
                ignore_https_errors=True
            )
            
            page = await self.context.new_page()
            # 共通のタイムアウト設定
            page.set_default_timeout(self.timeout)
            
            return self.browser, self.context, page
        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {e}")
            await self.close()
            raise

    async def navigate(self, page: Page, url: str, wait_until: str = "networkidle", retries: int = 2, strategy: Optional[Any] = None) -> bool:
        """
        ドメインごとのレートリミットを順守しつつ、指定されたURLにページ遷移する。
        失敗した場合はリトライおよび動的待機戦略をサポート。
        """
        # レートリミット（スリープ）の適用
        await self.rate_limiter.throttle(url, custom_delay=self.delay)
        
        for attempt in range(1, retries + 2):
            try:
                self.logger.info(f"Navigating to {url} (Attempt {attempt}/{retries + 1})")
                await page.goto(url, wait_until=wait_until, timeout=self.timeout)
                
                # カスタム待機戦略がある場合は適用
                if strategy:
                    self.logger.info(f"Applying dynamic strategy: {strategy.__class__.__name__}")
                    await strategy.wait_for_content(page)
                else:
                    # デフォルトの待機戦略: 重要な要素（body等）の出現を待機
                    try:
                        await page.wait_for_selector("body", timeout=5000)
                    except Exception:
                        self.logger.debug("Default body selector wait timed out, proceeding anyway")
                    
                return True
            except Exception as e:
                self.logger.warning(f"Failed to navigate to {url} on attempt {attempt}: {e}")
                if attempt <= retries:
                    await asyncio.sleep(2 ** attempt)  # 指数バックオフ
                else:
                    self.logger.error(f"Max retries reached for navigating to {url}")
        return False

    async def wait_for_dynamic_content(self, page: Page, selector: str, timeout: Optional[int] = None) -> bool:
        """
        指定したセレクタが表示されるまで待機する共通メソッド。
        """
        t = timeout if timeout else self.timeout
        try:
            await page.wait_for_selector(selector, state="visible", timeout=t)
            return True
        except Exception as e:
            self.logger.warning(f"Timeout waiting for selector {selector}: {e}")
            return False

    @abstractmethod
    async def extract_links(self, html: str, base_url: str, agency_name: str = "不明") -> List[Any]:
        """
        ページ内の入札案件またはPDFファイルへのリンクを抽出する抽象メソッド。
        各クローラー実装クラスでオーバーライドする。
        """
        pass

    async def extract_links_with_fallback(self, html: str, base_url: str, agency_name: str = "不明") -> List[Any]:
        """
        特化クローラなどの高度な抽出を試み、失敗または結果が少なすぎる場合に
        共通のリンク抽出メソッド（フォールバック）を使用する。
        """
        try:
            # まずは実装クラスの特化抽出を試みる
            results = await self.extract_links(html, base_url, agency_name)
            
            # 結果が空、あるいは極端に少ない（例: 1件未満）場合はフォールバックを検討
            if not results or len(results) < 1:
                self.logger.info(f"Low result count ({len(results)}) for {agency_name}. Triggering fallback extraction.")
                fallback_results = self._extract_absolute_urls(html, base_url)
                # 抽出結果を統合（重複排除が必要な場合はここで実施）
                return fallback_results if fallback_results else results
                
            return results
        except Exception as e:
            self.logger.error(f"Error in primary extraction for {agency_name}: {e}. Using fallback.")
            return self._extract_absolute_urls(html, base_url)

    def _extract_absolute_urls(self, html: Any, base_url: str) -> List[Dict[str, Any]]:
        """
        HTMLから絶対URLを抽出し、正規化する共通ユーティリティ。
        """
        from urllib.parse import urljoin, urlparse
        from bs4 import BeautifulSoup

        links = []
        soup = BeautifulSoup(html, 'html.parser')
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(base_url, href)
            text = a_tag.get_text(strip=True) or "No text"
            
            # 重複排除と正規化（フラグメント除去）
            normalized_url = full_url.split('#')[0].rstrip('/')
            
            links.append({
                'url': normalized_url,
                'text': text
            })
        return links

    def _detect_pagination_links(self, html: Any, base_url: str) -> List[Dict[str, Any]]:
        """
        HTMLからページネーションリンク（「次へ」「次ページ」等）を検出する。
        """
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        pagination_keywords = ["次へ", "次ページ", "Next", "＞", ">>", "次へ進む"]
        found_links = []
        soup = BeautifulSoup(html, 'html.parser')
        
        for a_tag in soup.find_all('a', href=True):
            text = a_tag.get_text(strip=True)
            if any(keyword in text for keyword in pagination_keywords):
                full_url = urljoin(base_url, a_tag['href'])
                found_links.append({
                    'url': full_url.split('#')[0].rstrip('/'),
                    'text': text
                })
        
        return found_links

    async def close(self) -> None:
        """
        Playwright関連のリソースをクローズする。
        """
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            self.logger.error(f"Error during close: {e}")
        finally:
            self.context = None
            self.browser = None
            self.playwright = None
    
    async def fetch_page(self, url: str) -> Any:
        """
        フォールバックサポート付きでページをフェッチする。
        設定に基づいてPlaywrightまたはrequestsを使用し、失敗時はフォールバックする。
        """
        # HTTPクライアントを使用してフォールバックサポート付きでフェッチ
        return await self.hybrid_client.fetch_page(url)
    
    async def fetch_page_with_playwright(self, url: str, headless: bool = True) -> bool:
        """
        Playwright専用でページをフェッチ（既存のnavigateロジックを使用）。
        Returns: 成功したかどうか
        """
        if not self.browser or not self.context:
            await self.init_browser(headless=headless)
        
        page = await self.context.new_page()
        try:
            # レートリミット（スリープ）の適用
            await self.rate_limiter.throttle(url, custom_delay=self.delay)
            
            for attempt in range(1, self.config.fallback.retry_on_playwright + 2):
                try:
                    self.logger.info(f"Navigating to {url} with Playwright (Attempt {attempt}/{self.config.fallback.retry_on_playwright + 1})")
                    await page.goto(url, wait_until="networkidle", timeout=self.timeout)
                    return True
                except Exception as e:
                    self.logger.warning(f"Failed to navigate to {url} with Playwright on attempt {attempt}: {e}")
                    if attempt <= self.config.fallback.retry_on_playwright:
                        await asyncio.sleep(2 ** attempt)  # 指数バックオフ
                    else:
                        self.logger.error(f"Max retries reached for navigating to {url} with Playwright")
            return False
        finally:
            await page.close()
