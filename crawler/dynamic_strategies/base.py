# 改善点3 ステップ58-66: 動的レンダリング待機戦略の実装

import asyncio
from abc import ABC, abstractmethod
from playwright.async_api import Page

class DynamicStrategy(ABC):
    """
    ページ遷移後のコンテンツ待機戦略のための抽象基底クラス。
    """
    @abstractmethod
    async def wait_for_content(self, page: Page):
        """
        ページが完全に読み込まれ、解析可能になるまで待機する。
        """
        pass

class NetworkIdleStrategy(DynamicStrategy):
    """
    ネットワークリクエストがアイドル状態になるまで待機する戦略。
    """
    async def wait_for_content(self, page: Page):
        try:
            # networkidle: 少なくとも500msの間、ネットワーク接続が0件になるまで待機
            await page.wait_for_load_state('networkidle', timeout=30000)
        except Exception as e:
            print(f"NetworkIdleStrategy timeout or error: {e}")

class KeywordWaitStrategy(DynamicStrategy):
    """
    特定のセレクタやテキストが出現するまで待機する戦略。
    """
    def __init__(self, selector: str, timeout: int = 15000):
        self.selector = selector
        self.timeout = timeout

    async def wait_for_content(self, page: Page):
        try:
            await page.wait_for_selector(self.selector, state='visible', timeout=self.timeout)
        except Exception as e:
            print(f"KeywordWaitStrategy timeout or error for {self.selector}: {e}")
