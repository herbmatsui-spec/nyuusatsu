"""Tests for Date Filter utility."""

import pytest
from datetime import date
from crawler.utils.date_filter import (
    filter_by_date_range,
    should_stop_early,
)


class TestFilterByDateRange:
    """filter_by_date_range のテスト。"""

    @pytest.fixture
    def sample_items(self):
        """テスト用アイテム"""
        return [
            {"id": 1, "item_date": date(2024, 1, 15)},
            {"id": 2, "item_date": date(2024, 2, 15)},
            {"id": 3, "item_date": date(2024, 3, 15)},
            {"id": 4, "item_date": date(2024, 4, 15)},
            {"id": 5, "item_date": date(2024, 5, 15)},
        ]

    @pytest.fixture
    def date_extractor(self):
        def extract(item):
            return item.get("item_date")
        return extract

    def test_no_filter(self, sample_items, date_extractor):
        """フィルタなし"""
        result = filter_by_date_range(sample_items, None, None, date_extractor)
        assert len(result) == 5

    def test_start_date_only(self, sample_items, date_extractor):
        """開始日のみ"""
        result = filter_by_date_range(sample_items, date(2024, 3, 1), None, date_extractor)
        assert len(result) == 3
        assert all(item["item_date"] >= date(2024, 3, 1) for item in result)

    def test_end_date_only(self, sample_items, date_extractor):
        """終了日のみ"""
        result = filter_by_date_range(sample_items, None, date(2024, 3, 31), date_extractor)
        assert len(result) == 3
        assert all(item["item_date"] <= date(2024, 3, 31) for item in result)

    def test_both_dates(self, sample_items, date_extractor):
        """開始日と終了日"""
        result = filter_by_date_range(sample_items, date(2024, 2, 1), date(2024, 4, 30), date_extractor)
        assert len(result) == 3
        assert all(date(2024, 2, 1) <= item["item_date"] <= date(2024, 4, 30) for item in result)

    def test_exact_match_included(self, sample_items, date_extractor):
        """境界値は含まれる"""
        result = filter_by_date_range(sample_items, date(2024, 3, 15), date(2024, 3, 15), date_extractor)
        assert len(result) == 1
        assert result[0]["id"] == 3

    def test_none_date_included(self, date_extractor):
        """日付が None のアイテムは含まれる（保守的）"""
        items = [
            {"id": 1, "item_date": date(2024, 1, 15)},
            {"id": 2, "item_date": None},
            {"id": 3, "item_date": date(2024, 3, 15)},
        ]
        result = filter_by_date_range(items, date(2024, 2, 1), None, date_extractor)
        assert len(result) == 2  # None と 3/15 が含まれる

    def test_extractor_exception_included(self, date_extractor):
        """抽出関数で例外が発生した場合は含まれる（保守的）"""
        def bad_extractor(item):
            if item["id"] == 2:
                raise ValueError("Parse error")
            return item["item_date"]
        
        items = [
            {"id": 1, "item_date": date(2024, 2, 15)},  # start_date 以降
            {"id": 2, "item_date": date(2024, 2, 15)},
            {"id": 3, "item_date": date(2024, 3, 15)},
        ]
        # start_date = 2024-02-01 なので、id=1 は範囲内、id=2 は例外で含まれる、id=3 は範囲内
        result = filter_by_date_range(items, date(2024, 2, 1), None, bad_extractor)
        assert len(result) == 3  # すべて含まれる

    def test_empty_list(self, date_extractor):
        """空リスト"""
        result = filter_by_date_range([], date(2024, 1, 1), None, date_extractor)
        assert result == []


class TestShouldStopEarly:
    """should_stop_early のテスト。"""

    @pytest.fixture
    def date_extractor(self):
        def extract(item):
            return item.get("item_date")
        return extract

    def test_all_older(self, date_extractor):
        """すべて start_date より古い"""
        items = [
            {"item_date": date(2024, 1, 10)},
            {"item_date": date(2024, 1, 5)},
            {"item_date": date(2024, 1, 1)},
        ]
        assert should_stop_early(items, date(2024, 1, 15), date_extractor) is True

    def test_some_in_range(self, date_extractor):
        """範囲内のアイテムがある"""
        items = [
            {"item_date": date(2024, 1, 10)},
            {"item_date": date(2024, 1, 20)},  # 範囲内
            {"item_date": date(2024, 1, 5)},
        ]
        assert should_stop_early(items, date(2024, 1, 15), date_extractor) is False

    def test_empty_list(self, date_extractor):
        """空リスト"""
        assert should_stop_early([], date(2024, 1, 15), date_extractor) is False

    def test_none_date_continues(self, date_extractor):
        """日付不明のアイテムがある場合は継続"""
        items = [
            {"item_date": date(2024, 1, 10)},
            {"item_date": None},
        ]
        assert should_stop_early(items, date(2024, 1, 15), date_extractor) is False

    def test_extractor_exception_continues(self, date_extractor):
        """抽出関数で例外が発生した場合は継続"""
        def bad_extractor(item):
            if item["id"] == 2:
                raise ValueError("Parse error")
            return item["item_date"]
        
        items = [
            {"id": 1, "item_date": date(2024, 1, 10)},
            {"id": 2, "item_date": date(2024, 1, 5)},
        ]
        assert should_stop_early(items, date(2024, 1, 15), bad_extractor) is False

    def test_newest_first_assumption(self, date_extractor):
        """新しい順（降順）で並んでいる前提のテスト"""
        # 降順の場合、最初のアイテムが範囲内なら継続
        items = [
            {"item_date": date(2024, 2, 1)},  # 最新
            {"item_date": date(2024, 1, 15)},
            {"item_date": date(2024, 1, 1)},
        ]
        assert should_stop_early(items, date(2024, 1, 20), date_extractor) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])