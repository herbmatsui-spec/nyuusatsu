"""ページ遷移待機の明示的待機化 (Step 23)。

Playwright / requests-html 互換の待機戦略を提供。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


async def wait_for_selector(
    page: Any,
    selector: str,
    timeout: int = 30000,
    state: str = "attached",
) -> Any:
    """Playwright page でセレクタを待機する。

    Args:
        page: Playwright Page
        selector: CSS セレクタ
        timeout: 最大待機時間 (ミリ秒)
        state: 待機条件 ("attached", "detached", "visible", "hidden")

    Returns:
        マッチした要素、または None
    """
    try:
        element = await page.wait_for_selector(selector, timeout=timeout, state=state)
        logger.debug(f"Selector '{selector}' found (state={state})")
        return element
    except Exception as e:
        logger.warning(f"Timeout waiting for selector '{selector}': {e}")
        return None


async def wait_for_load_state(
    page: Any,
    state: str = "networkidle",
    timeout: int = 30000,
) -> bool:
    """Playwright page で読み込み状態を待機する。

    Args:
        page: Playwright Page
        state: 待機状態 ("load", "domcontentloaded", "networkidle")
        timeout: 最大待機時間 (ミリ秒)

    Returns:
        成功時 True
    """
    try:
        await page.wait_for_load_state(state, timeout=timeout)
        logger.debug(f"Load state '{state}' reached")
        return True
    except Exception as e:
        logger.warning(f"Timeout waiting for load state '{state}': {e}")
        return False


async def wait_for_condition(
    condition: Callable[[], Awaitable[bool]],
    timeout: int = 30000,
    interval: int = 500,
) -> bool:
    """任意の非同期条件が真になるまで待機する。

    Args:
        condition: 真偽を返す非同期関数
        timeout: 最大待機時間 (ミリ秒)
        interval: ポーリング間隔 (ミリ秒)

    Returns:
        条件が満たされた場合 True、タイムアウト時 False
    """
    start = asyncio.get_event_loop().time() * 1000
    while True:
        try:
            if await condition():
                return True
        except Exception:
            pass
        elapsed = asyncio.get_event_loop().time() * 1000 - start
        if elapsed >= timeout:
            logger.warning(f"Timeout waiting for condition after {timeout}ms")
            return False
        await asyncio.sleep(interval / 1000)
    return False


async def wait_for_navigation(
    page: Any,
    timeout: int = 30000,
    wait_until: str = "networkidle",
) -> bool:
    """ナビゲーション完了を待機する。

    Args:
        page: Playwright Page
        timeout: 最大待機時間 (ミリ秒)
        wait_until: 待機条件 ("load", "domcontentloaded", "networkidle", "commit")

    Returns:
        成功時 True
    """
    try:
        await page.wait_for_load_state(wait_until, timeout=timeout)
        logger.debug(f"Navigation complete (wait_until={wait_until})")
        return True
    except Exception as e:
        logger.warning(f"Navigation timeout: {e}")
        return False


async def wait_with_fallback(
    page: Any,
    primary_selectors: list[str],
    fallback_states: Optional[list[str]] = None,
    timeout: int = 30000,
) -> Any:
    """プライマリセレクタで待機し、失敗時はフォールバック状態を試す。

    Args:
        page: Playwright Page
        primary_selectors: 試行するセレクタのリスト
        fallback_states: フォールバック用の待機状態リスト
        timeout: 最大待機時間 (ミリ秒)

    Returns:
        マッチした要素、または None
    """
    if fallback_states is None:
        fallback_states = ["networkidle", "load", "domcontentloaded"]

    for selector in primary_selectors:
        element = await wait_for_selector(page, selector, timeout=timeout)
        if element:
            return element

    # セレクタが見つからない場合、ページ読み込み待機でフォールバック
    for state in fallback_states:
        if await wait_for_load_state(page, state=state, timeout=timeout):
            # 読み込み完了後に再試行
            for selector in primary_selectors:
                element = await wait_for_selector(page, selector, timeout=5000)
                if element:
                    return element
    return None