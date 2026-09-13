"""Tests for Field Normalizer utilities."""

import pytest
from datetime import date
from crawler.parsers.field_normalizer import (
    normalize_amount,
    normalize_date,
    normalize_whitespace,
    normalize_fullwidth_to_halfwidth,
    TRANSFORM_MAP,
)


class TestNormalizeAmount:
    """normalize_amount のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("1,234,567円", 1234567),
        ("1,234,567", 1234567),
        ("¥1,234,567", 1234567),
        ("1234567", 1234567),
        (" 1,234,567 ", 1234567),
        ("金額 1,000,000 円", 1000000),
        ("", 0),
        ("円", 0),
        ("abc", 0),
        ("1,2,3,4", 1234),
        ("１２３", 123),  # 全角数字も除去されて残る
        ("-1,000", 1000),  # マイナス記号は除去
    ])
    def test_amount_normalization(self, text, expected):
        assert normalize_amount(text) == expected


class TestNormalizeDate:
    """normalize_date のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("2024.04.01", date(2024, 4, 1)),
        ("2024/04/01", date(2024, 4, 1)),
        ("2024-04-01", date(2024, 4, 1)),
        ("20240401", date(2024, 4, 1)),
        (" 2024.04.01 ", date(2024, 4, 1)),
        ("2024/4/1", date(2024, 4, 1)),
        ("2024-4-1", date(2024, 4, 1)),
        ("", None),
        ("invalid", None),
        ("2024/13/01", None),
        ("2024/02/30", None),
        ("2024.13.01", None),
        ("01/04/2024", None),  # DD/MM/YYYY は非対応
    ])
    def test_date_normalization(self, text, expected):
        assert normalize_date(text) == expected


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
        ("full　width　space", "full width space"),  # 全角スペースも分割
    ])
    def test_whitespace_normalization(self, text, expected):
        assert normalize_whitespace(text) == expected


class TestNormalizeFullwidthToHalfwidth:
    """normalize_fullwidth_to_halfwidth のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("１２３４５", "12345"),
        ("ＡＢＣＤ", "ABCD"),
        ("１２３ＡＢＣ", "123ABC"),
        ("Ｈｅｌｌｏ", "Hello"),
        ("１２３＆ＡＢＣ", "123&ABC"),
        ("", ""),
        ("123ABC", "123ABC"),  # 半角はそのまま
        ("テスト", "テスト"),  # 日本語は変換対象外
        ("テスト１２３", "テスト123"),
    ])
    def test_fullwidth_to_halfwidth(self, text, expected):
        result = normalize_fullwidth_to_halfwidth(text)
        assert result == expected


class TestTransformMap:
    """TRANSFORM_MAP のテスト。"""

    def test_transform_map_keys(self):
        """必要なキーがすべて存在することを確認。"""
        expected_keys = {
            "normalize_amount",
            "normalize_date",
            "normalize_whitespace",
            "normalize_fullwidth_to_halfwidth",
        }
        assert set(TRANSFORM_MAP.keys()) == expected_keys

    def test_transform_map_functions_callable(self):
        """すべての関数が呼び出し可能であることを確認。"""
        for name, func in TRANSFORM_MAP.items():
            assert callable(func), f"{name} is not callable"

    def test_transform_map_integration(self):
        """TRANSFORM_MAP 経由での呼び出しテスト。"""
        # normalize_amount
        result = TRANSFORM_MAP["normalize_amount"]("1,234円")
        assert result == 1234

        # normalize_date
        result = TRANSFORM_MAP["normalize_date"]("2024.04.01")
        assert result == date(2024, 4, 1)

        # normalize_whitespace
        result = TRANSFORM_MAP["normalize_whitespace"]("  a  b  ")
        assert result == "a b"

        # normalize_fullwidth_to_halfwidth
        result = TRANSFORM_MAP["normalize_fullwidth_to_halfwidth"]("１２３")
        assert result == "123"


class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_normalize_amount_large_number(self):
        """大きな数値。"""
        result = normalize_amount("9,999,999,999円")
        assert result == 9999999999

    def test_normalize_amount_only_commas(self):
        """カンマのみ。"""
        assert normalize_amount(",,,,") == 0

    def test_normalize_date_year_only(self):
        """年だけの文字列。"""
        assert normalize_date("2024") is None

    def test_normalize_whitespace_preserves_internal(self):
        """内部スペースは保持される。"""
        assert normalize_whitespace("a  b") == "a b"  # 連続スペースは1つに
        assert normalize_whitespace("a b") == "a b"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])