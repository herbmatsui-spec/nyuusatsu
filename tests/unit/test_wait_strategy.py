"""Tests for Wait Strategy utility."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from crawler.utils.wait_strategy import (
    wait_for_selector,
    wait_for_load_state,
    wait_for_condition,
    wait_for_navigation,
    wait_with_fallback,
)


class MockPage:
    """Playwright Page のモック"""
    def __init__(self):
        self.wait_for_selector = AsyncMock()
        self.wait_for_load_state = AsyncMock()
        self.query_selector = AsyncMock()
        self.query_selector_all = AsyncMock()


class TestWaitForSelector:
    """wait_for_selector のテスト。"""

    @pytest.mark.asyncio
    async def test_success(self):
        page = MockPage()
        mock_element = MagicMock()
        page.wait_for_selector.return_value = mock_element
        
        result = await wait_for_selector(page, ".test-selector")
        
        assert result == mock_element
        page.wait_for_selector.assert_called_once_with(".test-selector", timeout=30000, state="attached")

    @pytest.mark.asyncio
    async def test_custom_params(self):
        page = MockPage()
        mock_element = MagicMock()
        page.wait_for_selector.return_value = mock_element
        
        result = await wait_for_selector(page, ".custom", timeout=5000, state="visible")
        
        assert result == mock_element
        page.wait_for_selector.assert_called_once_with(".custom", timeout=5000, state="visible")

    @pytest.mark.asyncio
    async def test_timeout(self):
        page = MockPage()
        page.wait_for_selector.side_effect = Exception("Timeout")
        
        result = await wait_for_selector(page, ".missing")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_logging(self, caplog):
        page = MockPage()
        page.wait_for_selector.side_effect = Exception("Timeout")
        
        await wait_for_selector(page, ".missing")
        
        assert "Timeout waiting for selector '.missing'" in caplog.text


class TestWaitForLoadState:
    """wait_for_load_state のテスト。"""

    @pytest.mark.asyncio
    async def test_success(self):
        page = MockPage()
        
        result = await wait_for_load_state(page)
        
        assert result is True
        page.wait_for_load_state.assert_called_once_with("networkidle", timeout=30000)

    @pytest.mark.asyncio
    async def test_custom_params(self):
        page = MockPage()
        
        result = await wait_for_load_state(page, state="load", timeout=5000)
        
        assert result is True
        page.wait_for_load_state.assert_called_once_with("load", timeout=5000)

    @pytest.mark.asyncio
    async def test_timeout(self):
        page = MockPage()
        page.wait_for_load_state.side_effect = Exception("Timeout")
        
        result = await wait_for_load_state(page)
        
        assert result is False


class TestWaitForCondition:
    """wait_for_condition のテスト。"""

    @pytest.mark.asyncio
    async def test_immediate_true(self):
        async def condition():
            return True
        
        result = await wait_for_condition(condition, timeout=1000)
        assert result is True

    @pytest.mark.asyncio
    async def test_eventually_true(self):
        call_count = [0]
        
        async def condition():
            call_count[0] += 1
            return call_count[0] >= 3
        
        result = await wait_for_condition(condition, timeout=5000, interval=10)
        assert result is True
        assert call_count[0] >= 3

    @pytest.mark.asyncio
    async def test_timeout(self):
        async def condition():
            return False
        
        result = await wait_for_condition(condition, timeout=100, interval=10)
        assert result is False

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        call_count = [0]
        
        async def condition():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Error")
            return True
        
        result = await wait_for_condition(condition, timeout=5000, interval=10)
        assert result is True


class TestWaitForNavigation:
    """wait_for_navigation のテスト。"""

    @pytest.mark.asyncio
    async def test_success(self):
        page = MockPage()
        
        result = await wait_for_navigation(page)
        
        assert result is True
        page.wait_for_load_state.assert_called_once_with("networkidle", timeout=30000)

    @pytest.mark.asyncio
    async def test_custom_params(self):
        page = MockPage()
        
        result = await wait_for_navigation(page, wait_until="load", timeout=5000)
        
        assert result is True
        page.wait_for_load_state.assert_called_once_with("load", timeout=5000)

    @pytest.mark.asyncio
    async def test_timeout(self):
        page = MockPage()
        page.wait_for_load_state.side_effect = Exception("Timeout")
        
        result = await wait_for_navigation(page)
        assert result is False


class TestWaitWithFallback:
    """wait_with_fallback のテスト。"""

    @pytest.mark.asyncio
    async def test_primary_success(self):
        page = MockPage()
        mock_element = MagicMock()
        page.wait_for_selector.return_value = mock_element
        
        result = await wait_with_fallback(page, [".primary", ".fallback"])
        
        assert result == mock_element
        page.wait_for_selector.assert_called_once_with(".primary", timeout=30000, state="attached")

    @pytest.mark.asyncio
    async def test_primary_fail_fallback_success(self):
        page = MockPage()
        mock_element = MagicMock()
        
        # 最初のセレクタは失敗、2番目は成功
        call_count = [0]
        async def selector_side_effect(selector, timeout=30000, state="attached"):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Not found")
            return mock_element
        
        page.wait_for_selector.side_effect = selector_side_effect
        page.wait_for_load_state.return_value = True
        
        result = await wait_with_fallback(page, [".primary", ".fallback"])
        
        assert result == mock_element
        assert page.wait_for_selector.call_count == 2

    @pytest.mark.asyncio
    async def test_all_fail_load_state_success(self):
        page = MockPage()
        mock_element = MagicMock()
        
        # すべてのセレクタが失敗、load_state は成功、再試行で成功
        call_count = [0]
        async def selector_side_effect(selector, timeout=30000, state="attached"):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Not found")
            return mock_element
        
        page.wait_for_selector.side_effect = selector_side_effect
        page.wait_for_load_state.return_value = True
        
        result = await wait_with_fallback(page, [".primary", ".fallback"])
        
        assert result == mock_element

    @pytest.mark.asyncio
    async def test_all_fail(self):
        page = MockPage()
        page.wait_for_selector.side_effect = Exception("Not found")
        page.wait_for_load_state.return_value = False
        
        result = await wait_with_fallback(page, [".primary", ".fallback"])
        
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])