"""バックフィル日付範囲クロールのテスト"""
import pytest
from datetime import date
from unittest.mock import Mock, patch, AsyncMock

from crawler.utils.date_parser import parse_date_string, extract_date_from_text
from crawler.utils.date_filter import filter_by_date_range, should_stop_early
from crawler.base_crawler import BaseCrawler


class MockCrawler(BaseCrawler):
    """テスト用の具象クラス"""
    def parse_list(self, html: str):
        return []
    
    def parse_detail(self, html: str):
        return None
    
    def save(self, items: list):
        pass

    def extract_item_date(self, item):
        return None


class TestDateParser:
    """日付パース機能のテスト"""

    def test_parse_iso_date(self):
        assert parse_date_string("2024-01-15") == date(2024, 1, 15)
        assert parse_date_string("2024/01/15") == date(2024, 1, 15)
        assert parse_date_string("2024.01.15") == date(2024, 1, 15)

    def test_parse_japanese_date(self):
        assert parse_date_string("2024年1月15日") == date(2024, 1, 15)
        assert parse_date_string("令和6年1月15日") == date(2024, 1, 15)
        assert parse_date_string("平成31年3月31日") == date(2019, 3, 31)
        assert parse_date_string("昭和63年1月1日") == date(1988, 1, 1)

    def test_parse_wareki_short(self):
        assert parse_date_string("R6.1.15") == date(2024, 1, 15)
        assert parse_date_string("H31.3.31") == date(2019, 3, 31)
        assert parse_date_string("S63.1.1") == date(1988, 1, 1)

    def test_parse_compact(self):
        assert parse_date_string("20240115") == date(2024, 1, 15)

    def test_parse_invalid(self):
        assert parse_date_string("") is None
        assert parse_date_string("invalid") is None
        assert parse_date_string(None) is None

    def test_extract_from_text(self):
        text = "公告日: 2024-01-15 案件名: テスト"
        assert extract_date_from_text(text) == date(2024, 1, 15)

        text = "令和6年2月1日に公告されました"
        assert extract_date_from_text(text) == date(2024, 2, 1)


class TestDateFilter:
    """日付フィルタ機能のテスト"""

    def make_item(self, d: str):
        """テスト用アイテム作成"""
        item = Mock()
        item.announcement_date = d
        return item

    def date_extractor(self, item):
        # Mockオブジェクトの場合、announcement_date が Mock になる可能性があるため
        # 文字列として取得を試みる
        val = getattr(item, 'announcement_date', None)
        if val is None:
            return None
        # Mockオブジェクトの場合は str() すると "<Mock...>" になるので、
        # 文字列の場合のみパース
        if isinstance(val, str):
            return parse_date_string(val)
        return None

    def test_filter_by_start_date(self):
        items = [
            self.make_item("2024-01-15"),
            self.make_item("2024-02-15"),
            self.make_item("2023-12-15"),
        ]
        filtered = filter_by_date_range(items, date(2024, 1, 1), None, self.date_extractor)
        assert len(filtered) == 2
        assert parse_date_string(str(filtered[0].announcement_date)) >= date(2024, 1, 1)

    def test_filter_by_end_date(self):
        items = [
            self.make_item("2024-01-15"),
            self.make_item("2024-02-15"),
            self.make_item("2024-03-15"),
        ]
        # end_date=2024-02-01 なので 2024-01-15 のみ含まれる（2024-02-15 は除外）
        filtered = filter_by_date_range(items, None, date(2024, 2, 1), self.date_extractor)
        assert len(filtered) == 1
        assert parse_date_string(str(filtered[0].announcement_date)) <= date(2024, 2, 1)

    def test_filter_by_range(self):
        items = [
            self.make_item("2023-12-15"),
            self.make_item("2024-01-15"),
            self.make_item("2024-02-15"),
            self.make_item("2024-03-15"),
        ]
        filtered = filter_by_date_range(
            items, date(2024, 1, 1), date(2024, 2, 28), self.date_extractor
        )
        assert len(filtered) == 2

    def test_should_stop_early_all_older(self):
        """すべてのアイテムが start_date より古い場合"""
        items = [
            self.make_item("2023-12-15"),
            self.make_item("2023-11-15"),
        ]
        assert should_stop_early(items, date(2024, 1, 1), self.date_extractor) is True

    def test_should_stop_early_has_newer(self):
        """範囲内のアイテムがある場合"""
        items = [
            self.make_item("2024-01-15"),
            self.make_item("2023-12-15"),
        ]
        assert should_stop_early(items, date(2024, 1, 1), self.date_extractor) is False

    def test_should_stop_early_empty(self):
        """空リストの場合"""
        assert should_stop_early([], date(2024, 1, 1), self.date_extractor) is False

    def test_filter_unknown_date_included(self):
        """日付不明のアイテムは含まれる（保守的）"""
        items = [
            self.make_item("2024-01-15"),
            Mock(announcement_date=None),  # 日付なし
        ]
        filtered = filter_by_date_range(items, date(2024, 1, 1), None, self.date_extractor)
        assert len(filtered) == 2


class TestBaseCrawlerDateRange:
    """BaseCrawlerの日付範囲機能テスト"""

    def test_init_with_dates(self):
        crawler = MockCrawler(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
        assert crawler.start_date == date(2024, 1, 1)
        assert crawler.end_date == date(2024, 12, 31)

    def test_init_without_dates(self):
        crawler = MockCrawler()
        assert crawler.start_date is None
        assert crawler.end_date is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])