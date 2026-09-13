"""Tests for Text Cleaner utility."""

import pytest
from crawler.utils.text_cleaner import (
    normalize_whitespace,
    remove_html_tags,
    normalize_numbers,
    clean_amount_text,
    truncate,
)


class TestNormalizeWhitespace:
    """normalize_whitespace のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("  hello   world  ", "hello world"),
        ("hello\tworld", "hello world"),
        ("hello\nworld", "hello world"),
        ("  a  b  c  ", "a b c"),
        ("", ""),
        ("   ", ""),
        ("single", "single"),
        ("\t\n\r", ""),
        ("全角　スペース", "全角 スペース"),
        ("混在  \t\n  スペース", "混在 スペース"),
    ])
    def test_whitespace_normalization(self, text, expected):
        assert normalize_whitespace(text) == expected


class TestRemoveHtmlTags:
    """remove_html_tags のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("<p>Hello</p>", "Hello"),
        ("<div><span>Text</span></div>", "Text"),
        ("<br/>Line", "Line"),
        ("No tags", "No tags"),
        ("", ""),
        ("<p>Nested <b>bold</b> text</p>", "Nested bold text"),
        ("<script>alert('xss')</script>Safe", "Safe"),
        ("<img src='test.jpg'/>", ""),
    ])
    def test_html_tag_removal(self, text, expected):
        assert remove_html_tags(text) == expected


class TestNormalizeNumbers:
    """normalize_numbers のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("１２３４５", "12345"),
        ("１２３ＡＢＣ", "123ABC"),
        ("1,234,567", "1234567"),
        ("1，234，567", "1234567"),
        ("1.234.567", "1234567"),
        ("１．２３", "123"),
        ("1,234.56", "123456"),
        ("", ""),
        ("123", "123"),
    ])
    def test_number_normalization(self, text, expected):
        assert normalize_numbers(text) == expected


class TestCleanAmountText:
    """clean_amount_text のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("1,234,567円", 1234567),
        ("¥1,234,567", 1234567),
        ("￥1,234,567", 1234567),
        ("1234567", 1234567),
        ("  1,234,567  ", 1234567),
        ("１，２３４，５６７円", 1234567),
        ("", None),
        ("金額なし", None),
        ("---", None),
        ("1,234.56円", 123456),  # 小数点も除去される
    ])
    def test_amount_cleaning(self, text, expected):
        assert clean_amount_text(text) == expected


class TestTruncate:
    """truncate のテスト。"""

    def test_within_limit(self):
        assert truncate("short", 10) == "short"
        assert truncate("exact", 5) == "exact"

    def test_over_limit(self):
        assert truncate("verylongtext", 5) == "veryl"
        assert truncate("1234567890", 5) == "12345"

    def test_empty(self):
        assert truncate("", 10) == ""
        assert truncate(None, 10) == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])