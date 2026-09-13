"""Tests for Date Field Detector utility."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from crawler.utils.date_field_detector import (
    detect_date_field,
    DEFAULT_DATE_HEURISTIC,
)


class MockPage:
    """Playwright Page のモック"""
    def __init__(self):
        self.query_selector = AsyncMock()
        self.query_selector_all = AsyncMock()


class TestDetectDateField:
    """detect_date_field のテスト。"""

    @pytest.mark.asyncio
    async def test_configured_string_success(self):
        """設定済みセレクタ（文字列）で成功"""
        page = MockPage()
        mock_element = MagicMock()
        page.query_selector.return_value = mock_element
        
        result = await detect_date_field(page, "#start-date", "start_date")
        
        assert result == mock_element
        page.query_selector.assert_called_once_with("#start-date")

    @pytest.mark.asyncio
    async def test_configured_list_first_success(self):
        """設定済みセレクタ（リスト）で最初が成功"""
        page = MockPage()
        mock_element = MagicMock()
        page.query_selector.return_value = mock_element
        
        result = await detect_date_field(page, ["#first", "#second"], "start_date")
        
        assert result == mock_element
        page.query_selector.assert_called_once_with("#first")

    @pytest.mark.asyncio
    async def test_configured_list_second_success(self):
        """設定済みセレクタ（リスト）で2番目が成功"""
        page = MockPage()
        mock_element = MagicMock()
        
        call_count = [0]
        async def query_selector_side_effect(selector):
            call_count[0] += 1
            if call_count[0] == 1:
                return None
            return mock_element
        
        page.query_selector.side_effect = query_selector_side_effect
        
        result = await detect_date_field(page, ["#first", "#second"], "start_date")
        
        assert result == mock_element
        assert page.query_selector.call_count == 2

    @pytest.mark.asyncio
    async def test_configured_all_fail_fallback(self):
        """設定済みセレクタすべて失敗 → ヒューリスティック"""
        page = MockPage()
        mock_element = MagicMock()
        
        # query_selector はすべて None
        page.query_selector.return_value = None
        
        # query_selector_all でヒット
        page.query_selector_all.return_value = [mock_element, MagicMock()]
        
        result = await detect_date_field(page, "#configured", "start_date")
        
        assert result == mock_element
        page.query_selector.assert_called_once_with("#configured")
        # ヒューリスティックの最初のセレクタが呼ばれる
        page.query_selector_all.assert_called_once_with(DEFAULT_DATE_HEURISTIC[0])

    @pytest.mark.asyncio
    async def test_heuristic_multiple_elements_start_date(self):
        """ヒューリスティックで複数要素 → 最初の要素"""
        page = MockPage()
        page.query_selector.return_value = None
        
        elements = [MagicMock(), MagicMock(), MagicMock()]
        page.query_selector_all.return_value = elements
        
        result = await detect_date_field(page, None, "start_date")
        
        assert result == elements[0]

    @pytest.mark.asyncio
    async def test_heuristic_multiple_elements_end_date(self):
        """ヒューリスティックで複数要素 → 最後の要素"""
        page = MockPage()
        page.query_selector.return_value = None
        
        elements = [MagicMock(), MagicMock(), MagicMock()]
        page.query_selector_all.return_value = elements
        
        result = await detect_date_field(page, None, "end_date")
        
        assert result == elements[-1]

    @pytest.mark.asyncio
    async def test_heuristic_custom_list(self):
        """カスタムヒューリスティック"""
        page = MockPage()
        page.query_selector.return_value = None
        
        mock_element = MagicMock()
        custom_heuristic = ["custom1", "custom2"]
        page.query_selector_all.return_value = [mock_element]
        
        result = await detect_date_field(page, None, "start_date", heuristic=custom_heuristic)
        
        assert result == mock_element
        page.query_selector_all.assert_called_once_with("custom1")

    @pytest.mark.asyncio
    async def test_heuristic_all_fail(self):
        """ヒューリスティックもすべて失敗"""
        page = MockPage()
        page.query_selector.return_value = None
        page.query_selector_all.return_value = []
        
        result = await detect_date_field(page, None, "start_date")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """例外発生時は次のセレクタへ"""
        page = MockPage()
        mock_element = MagicMock()
        
        call_count = [0]
        async def query_selector_side_effect(selector):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Error")
            return mock_element
        
        page.query_selector.side_effect = query_selector_side_effect
        
        result = await detect_date_field(page, ["#first", "#second"], "start_date")
        
        assert result == mock_element

    def test_default_heuristic(self):
        """デフォルトヒューリスティックの確認"""
        expected = [
            'input.datepicker',
            'input[class*="datepicker"]',
            'input[id*="date" i]',
            'input[name*="date" i]',
            'input[placeholder*="日付" i]',
            'input[type="date"]',
        ]
        assert DEFAULT_DATE_HEURISTIC == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])