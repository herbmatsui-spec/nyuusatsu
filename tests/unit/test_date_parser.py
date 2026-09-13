"""Tests for Date Parser utility."""

import pytest
from datetime import date, datetime
from crawler.utils.date_parser import (
    parse_date_string,
    extract_date_from_text,
    parse_datetime_string,
)


class TestParseDateString:
    """parse_date_string のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("2024-01-15", date(2024, 1, 15)),
        ("2024/01/15", date(2024, 1, 15)),
        ("2024.01.15", date(2024, 1, 15)),
        ("2024年1月15日", date(2024, 1, 15)),
        ("2024年01月15日", date(2024, 1, 15)),
        ("令和6年1月15日", date(2024, 1, 15)),
        ("令和元年5月1日", date(2019, 5, 1)),
        ("平成31年4月1日", date(2019, 4, 1)),
        ("昭和63年1月1日", date(1988, 1, 1)),
        ("R6.1.15", date(2024, 1, 15)),
        ("H31.3.31", date(2019, 3, 31)),
        ("S63.1.1", date(1988, 1, 1)),
        ("20240115", date(2024, 1, 15)),
        ("01/15", date(datetime.now().year, 1, 15)),
        ("", None),
        (None, None),
        ("invalid", None),
    ])
    def test_date_parsing(self, text, expected):
        assert parse_date_string(text) == expected

    def test_with_prefix(self):
        """プレフィックス除去"""
        assert parse_date_string("公告日: 2024-01-15") == date(2024, 1, 15)
        assert parse_date_string("公告日：2024-01-15") == date(2024, 1, 15)
        assert parse_date_string("掲載日: 2024-01-15") == date(2024, 1, 15)
        assert parse_date_string("掲載日：2024-01-15") == date(2024, 1, 15)
        assert parse_date_string("発表日: 2024-01-15") == date(2024, 1, 15)
        assert parse_date_string("発表日：2024-01-15") == date(2024, 1, 15)
        assert parse_date_string("日付: 2024-01-15") == date(2024, 1, 15)

    def test_whitespace_handling(self):
        """前後の空白除去"""
        assert parse_date_string("  2024-01-15  ") == date(2024, 1, 15)
        assert parse_date_string("\t2024-01-15\n") == date(2024, 1, 15)

    def test_iso_format_fallback(self):
        """ISO形式フォールバック"""
        assert parse_date_string("2024-01-15T00:00:00") == date(2024, 1, 15)
        assert parse_date_string("2024/01/15T00:00:00") == date(2024, 1, 15)


class TestExtractDateFromText:
    """extract_date_from_text のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("公告日: 2024-01-15", date(2024, 1, 15)),
        ("掲載日: 2024/01/15", date(2024, 1, 15)),
        ("令和6年1月15日に公告", date(2024, 1, 15)),
        ("R6.1.15 発表", date(2024, 1, 15)),
        ("20240115 という日付", date(2024, 1, 15)),
        ("", None),
        (None, None),
        ("日付なし", None),
        ("来年も頑張ります", None),
    ])
    def test_extraction(self, text, expected):
        assert extract_date_from_text(text) == expected

    def test_first_match_priority(self):
        """最初に見つかった日付を返す"""
        text = "2024-01-15 と 2025-01-15"
        assert extract_date_from_text(text) == date(2024, 1, 15)


class TestParseDatetimeString:
    """parse_datetime_string のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("2024-01-15 10:30:00", datetime(2024, 1, 15, 10, 30, 0)),
        ("2024/01/15 10:30:00", datetime(2024, 1, 15, 10, 30, 0)),
        ("2024-01-15 10:30", datetime(2024, 1, 15, 10, 30)),
        ("2024/01/15 10:30", datetime(2024, 1, 15, 10, 30)),
        ("2024年1月15日 10時30分", datetime(2024, 1, 15, 10, 30)),
        ("2024-01-15T10:30:00", datetime(2024, 1, 15, 10, 30, 0)),
        ("2024-01-15", datetime(2024, 1, 15, 0, 0)),
        ("", None),
        (None, None),
        ("invalid", None),
    ])
    def test_datetime_parsing(self, text, expected):
        result = parse_datetime_string(text)
        assert result == expected

    def test_time_only_not_supported(self):
        """時間のみはサポートされていない（日付が必要）"""
        assert parse_datetime_string("10:30:00") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])