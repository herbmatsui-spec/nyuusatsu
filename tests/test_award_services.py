"""
Tests for award services (Phase3 Step30)
"""
import pytest

from services.award_calculator import (
    calculate_award_rate,
    enrich_award_rate,
    get_industry_avg_award_rate,
    get_overall_award_rate_stats,
    parse_amount_text,
)
from crawler.parsers.award_parser import (
    parse_budget_amount,
    parse_contract_amount,
    parse_date,
    parse_winner_name,
)
from crawler.utils.company_name_normalizer import (
    detect_industry,
    find_similar,
    normalize,
    remove_suffix,
)
from crawler.utils.text_cleaner import clean_amount_text


class TestAwardCalculator:
    def test_calculate_award_rate(self):
        assert calculate_award_rate(10000000, 9500000) == 95.0
        assert calculate_award_rate(100, 99) == 99.0
        assert calculate_award_rate(10000000, 0) is None
        assert calculate_award_rate(0, 5000000) is None
        assert calculate_award_rate(None, 5000000) is None

    def test_enrich_award_rate(self):
        d = {"budget_amount": 10000000, "contract_amount": 9500000}
        result = enrich_award_rate(d)
        assert "award_rate" in result
        assert result["award_rate"] == 95.0

    def test_parse_amount_text(self):
        assert parse_amount_text("12,345,678円") == 12345678
        assert parse_amount_text("") is None
        assert parse_amount_text("no digits") is None

    def test_clean_amount_text(self):
        assert clean_amount_text("12,345,678円") == 12345678


class TestCompanyNormalizer:
    def test_normalize(self):
        assert normalize("(株)サンプル") == "株式会社サンプル"
        assert normalize("㈱テスト") == "株式会社テスト"
        assert normalize("") == ""

    def test_remove_suffix(self):
        assert remove_suffix("株式会社サンプル建設") == "サンプル"
        assert remove_suffix("有限会社テスト") == "テスト"

    def test_detect_industry(self):
        assert detect_industry("道路建設工事") == "建設"
        assert detect_industry("システム開発業務") == "IT"
        assert detect_industry("不明") is None

    def test_find_similar(self):
        candidates = ["株式会社AAA", "株式会社BBB", "CCC"]
        assert find_similar("株式会社AAA", candidates) == "株式会社AAA"
        assert find_similar("ABC", ["XYZ"]) is None


class TestParserEdgeCases:
    def test_parse_budget_amount_various_formats(self):
        assert parse_budget_amount("10,000,000円") == 10000000
        assert parse_budget_amount("1000万円") is None
        assert parse_budget_amount(None) is None

    def test_parse_winner_name_edge_cases(self):
        assert parse_winner_name("落札者: (株)テスト") == "(株)テスト"
        assert parse_winner_name("") is None

    def test_parse_date_various(self):
        result = parse_date("2024/01/15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
