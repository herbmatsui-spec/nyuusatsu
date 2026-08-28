"""
Tests for Award Crawler (Phase2 Step 19)
"""
import pytest

from crawler.parsers.award_parser import (
    calculate_award_rate,
    extract_industry_from_text as detect_industry,
    parse_budget_amount,
    parse_contract_amount,
    parse_date,
    parse_winner_name,
)
from crawler.hokkaido.award_crawler import HokkaidoAwardCrawler
from config.award_urls import AWARD_URL_PATTERNS, get_award_list_url
from crawler.utils.company_name_normalizer import normalize, similarity, find_similar, remove_suffix
from crawler.utils.text_cleaner import clean_amount_text, normalize_whitespace


class TestAwardParser:
    def test_parse_budget_amount(self):
        assert parse_budget_amount("予定価格 12,345,678円") == 12345678
        assert parse_budget_amount("15,000,000円") == 15000000
        assert parse_budget_amount("") is None
        assert parse_budget_amount("no digits") is None

    def test_parse_contract_amount(self):
        assert parse_contract_amount("落札価格: 11,111,111円") == 11111111

    def test_calculate_award_rate(self):
        assert calculate_award_rate(10000000, 9500000) == 95.0
        assert calculate_award_rate(10000000, 10000000) == 100.0
        assert calculate_award_rate(10000000, 9000000) == 90.0
        assert calculate_award_rate(None, 9000000) is None
        assert calculate_award_rate(0, 9000000) is None

    def test_parse_date(self):
        from datetime import datetime
        result = parse_date("令和5年4月1日")
        assert result and result.year == 2023 and result.month == 4 and result.day == 1
        result = parse_date("2024/04/01")
        assert result and result.year == 2024 and result.month == 4 and result.day == 1
        assert parse_date("") is None

    def test_parse_winner_name(self):
        assert parse_winner_name("落札業者名：株式会社サンプル") == "株式会社サンプル"
        assert parse_winner_name("") is None

    def test_extract_industry_from_text(self):
        assert detect_industry("道路建設工事") == "建設"
        assert detect_industry("システム開発業務") == "IT"
        assert detect_industry("不明な案件") is None


class TestCompanyNormalizer:
    def test_normalize(self):
        assert normalize("(株)サンプル") == "株式会社サンプル"
        assert normalize("㈱テスト") == "株式会社テスト"
        assert normalize("株式会社  ABC  ") == "株式会社ABC"
        assert normalize("") == ""

    def test_remove_suffix(self):
        assert remove_suffix("株式会社サンプル建設") == "サンプル"
        assert remove_suffix("有限会社テスト") == "テスト"

    def test_similarity(self):
        assert similarity("株式会社ABC", "株式会社ABC") == 1.0
        assert similarity("ABC", "XYZ") < 1.0

    def test_find_similar(self):
        candidates = ["株式会社AAA", "株式会社BBB", "株式会社CCC"]
        result = find_similar("株式会社AAA", candidates)
        assert result == "株式会社AAA"


class TestTextCleaner:
    def test_clean_amount_text(self):
        assert clean_amount_text("12,345,678円") == 12345678
        assert clean_amount_text("") is None

    def test_normalize_whitespace(self):
        assert normalize_whitespace("a   b\n\tc") == "a b c"


class TestAwardURLConfig:
    def test_hokkaido_url_exists(self):
        assert "hokkaido" in AWARD_URL_PATTERNS
        url = get_award_list_url("hokkaido")
        assert url.startswith("https://")

    def test_get_award_list_url_unknown(self):
        assert get_award_list_url("unknown_pref") is None


class TestHokkaidoCrawler:
    def test_crawler_instantiation(self):
        c = HokkaidoAwardCrawler()
        assert c is not None

    def test_parse_detail_returns_dict(self):
        html = """
        <html><body>
        <p>予定価格: 10,000,000円</p>
        <p>落札価格: 9,500,000円</p>
        <p>落札業者名: 株式会社テスト</p>
        <p>令和5年4月1日</p>
        </body></html>
        """
        crawler = HokkaidoAwardCrawler()
        result = crawler.parse_award_detail(html)
        assert result is not None
        assert result["budget_amount"] == 10000000
        assert result["contract_amount"] == 9500000
        assert result["award_rate"] == 95.0
        assert "株式会社テスト" in (result.get("winner_name") or "")
