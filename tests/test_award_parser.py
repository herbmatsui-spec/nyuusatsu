"""Tests for Award Parser utilities."""

import pytest
from datetime import datetime
from crawler.parsers.award_parser import (
    parse_budget_amount,
    parse_contract_amount,
    calculate_award_rate,
    parse_date,
    parse_winner_name,
    extract_industry_from_text,
)


class TestParseBudgetAmount:
    """parse_budget_amount のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("予定価格 12,345,678円", 12345678),
        ("12,345,678円", 12345678),
        ("予定価格 1,000,000円", 1000000),
        ("¥1,234,567", 1234567),
        ("1234567", 1234567),
        ("  12,345  ", 12345),
        ("", None),
        (None, None),
        ("予定価格 なし", None),
        ("予定価格 ---", None),
        ("金額なし", None),
    ])
    def test_various_formats(self, text, expected):
        assert parse_budget_amount(text) == expected


class TestParseContractAmount:
    """parse_contract_amount のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("落札価格 11,111,111円", 11111111),
        ("契約金額 9,999,999円", 9999999),
        ("", None),
        (None, None),
    ])
    def test_various_formats(self, text, expected):
        assert parse_contract_amount(text) == expected


class TestCalculateAwardRate:
    """calculate_award_rate のテスト。"""

    @pytest.mark.parametrize("budget,contract,expected", [
        (10000000, 9500000, 95.0),
        (10000000, 10000000, 100.0),
        (10000000, 5000000, 50.0),
        (0, 9500000, None),
        (None, 9500000, None),
        (10000000, None, None),
        (10000000, 0, 0.0),
        (-1000, 5000, None),
    ])
    def test_rate_calculation(self, budget, contract, expected):
        assert calculate_award_rate(budget, contract) == expected


class TestParseDate:
    """parse_date のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("2024/04/01", datetime(2024, 4, 1)),
        ("2024-04-01", datetime(2024, 4, 1)),
        ("2024.04.01", datetime(2024, 4, 1)),
        ("2024年4月1日", datetime(2024, 4, 1)),
        ("2024年04月01日", datetime(2024, 4, 1)),
        ("令和6年4月1日", datetime(2024, 4, 1)),
        ("令和元年5月1日", datetime(2019, 5, 1)),
        ("令和 6 年 4 月 1 日", datetime(2024, 4, 1)),
        ("平成31年4月1日", datetime(2019, 4, 1)),
        ("平成元年1月8日", datetime(1989, 1, 8)),
        ("", None),
        (None, None),
        ("令和 年 月 日", None),
        ("invalid date", None),
    ])
    def test_date_parsing(self, text, expected):
        result = parse_date(text)
        assert result == expected


class TestParseWinnerName:
    """parse_winner_name のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("落札者：株式会社ABC", "株式会社ABC"),
        ("契約者：有限会社XYZ", "有限会社XYZ"),
        ("発注者：自治体A", "自治体A"),
        ("業者：株式会社テスト", "株式会社テスト"),
        ("供給者：サンプル株式会社", "サンプル株式会社"),
        ("  落札者：株式会社ABC  ", "株式会社ABC"),
        ("株式会社ABC", "株式会社ABC"),
        ("", None),
        (None, None),
        ("  ", None),
    ])
    def test_winner_name_extraction(self, text, expected):
        assert parse_winner_name(text) == expected


class TestExtractIndustryFromText:
    """extract_industry_from_text のテスト。"""

    @pytest.mark.parametrize("text,expected", [
        ("建設工事請負契約", "建設"),
        ("建築設計業務委託", "建設"),
        ("土木一式工事", "建設"),
        ("舗装工事", "建設"),
        ("管工事", "建設"),
        ("造園工事", "建設"),
        ("システム開発", "IT"),
        ("ソフトウェア開発", "IT"),
        ("ネットワーク構築", "IT"),
        ("データセンター運用", "IT"),
        ("クラウド移行", "IT"),
        ("コンサルティング業務", "コンサル"),
        ("調査業務", "コンサル"),
        ("計画設計", "コンサル"),
        ("物品購入", "物品"),
        ("備品調達", "物品"),
        ("機器購入", "物品"),
        ("委託業務", "委託"),
        ("業務委託", "委託"),
        ("サービス提供", "委託"),
        ("", None),
        (None, None),
        ("その他業務", "委託"),  # "業務" が委託キーワードに含まれる
    ])
    def test_industry_detection(self, text, expected):
        assert extract_industry_from_text(text) == expected


class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_unicode_numbers(self):
        """全角数字の処理。"""
        # 現在は全角数字も正しく処理される
        assert parse_budget_amount("１２３４５円") == 12345

    def test_mixed_separators(self):
        """混在セパレータの処理。"""
        # 最初の数字グループのみ抽出される
        assert parse_budget_amount("1,234.567") == 1234


if __name__ == "__main__":
    pytest.main([__file__, "-v"])