"""Tests for Forecast URL Detector utility."""

import pytest
from unittest.mock import patch, MagicMock
from crawler.utils.forecast_url_detector import (
    is_forecast_url,
    detect_forecast_in_text,
    extract_forecast_indicators,
    normalize_forecast_url,
    extract_agency_code_from_url,
    is_pdf_url,
    match_forecast_pattern,
)


class TestIsForecastUrl:
    """is_forecast_url のテスト。"""

    def test_empty_url(self):
        assert is_forecast_url("") is False
        assert is_forecast_url(None) is False

    def test_with_forecast_keyword(self):
        with patch("crawler.utils.forecast_url_detector.get_all_keywords", 
                   return_value=["yotei", "forecast", "plan"]):
            assert is_forecast_url("https://example.com/yotei.html") is True
            assert is_forecast_url("https://example.com/forecast") is True
            assert is_forecast_url("https://example.com/plan.html") is True

    def test_case_insensitive(self):
        with patch("crawler.utils.forecast_url_detector.get_all_keywords", 
                   return_value=["yotei"]):
            assert is_forecast_url("https://example.com/YOTEI.html") is True
            assert is_forecast_url("https://example.com/Yotei.html") is True

    def test_without_keyword(self):
        with patch("crawler.utils.forecast_url_detector.get_all_keywords", 
                   return_value=["yotei"]):
            assert is_forecast_url("https://example.com/other.html") is False


class TestDetectForecastInText:
    """detect_forecast_in_text のテスト。"""

    def test_empty_text(self):
        assert detect_forecast_in_text("") is False
        assert detect_forecast_in_text(None) is False

    def test_with_keyword(self):
        with patch("crawler.utils.forecast_url_detector.get_all_keywords", 
                   return_value=["発注見通し", "入札予定"]):
            assert detect_forecast_in_text("発注見通しについて") is True
            assert detect_forecast_in_text("入札予定を公開します") is True

    def test_without_keyword(self):
        with patch("crawler.utils.forecast_url_detector.get_all_keywords", 
                   return_value=["発注見通し"]):
            assert detect_forecast_in_text("通常のお知らせ") is False


class TestExtractForecastIndicators:
    """extract_forecast_indicators のテスト。"""

    def test_empty_text(self):
        assert extract_forecast_indicators("") == []
        assert extract_forecast_indicators(None) == []

    def test_extract_multiple(self):
        mock_patterns = [
            {"name": "group1", "keywords": ["発注見通し"], "priority": 1},
            {"name": "group2", "keywords": ["入札予定"], "priority": 2},
        ]
        with patch("crawler.utils.forecast_url_detector.FORECAST_URL_PATTERNS", mock_patterns):
            result = extract_forecast_indicators("発注見通しと入札予定があります")
            assert len(result) == 2
            assert any(h["keyword"] == "発注見通し" for h in result)
            assert any(h["keyword"] == "入札予定" for h in result)


class TestNormalizeForecastUrl:
    """normalize_forecast_url のテスト。"""

    def test_empty_url(self):
        assert normalize_forecast_url("") is None
        assert normalize_forecast_url(None) is None

    def test_basic_normalization(self):
        url = "https://example.com/path?query=1"
        result = normalize_forecast_url(url)
        assert result == "https://example.com/path?query=1"

    def test_trailing_slash_removed(self):
        url = "https://example.com/path/"
        result = normalize_forecast_url(url)
        assert result == "https://example.com/path"

    def test_with_fragment(self):
        # フラグメントは保持されない（urlparseの仕様）
        url = "https://example.com/path#section"
        result = normalize_forecast_url(url)
        assert result == "https://example.com/path"


class TestExtractAgencyCodeFromUrl:
    """extract_agency_code_from_url のテスト。"""

    def test_empty_url(self):
        assert extract_agency_code_from_url("") is None
        assert extract_agency_code_from_url(None) is None

    def test_path_pattern(self):
        assert extract_agency_code_from_url("https://example.com/123456/") == "123456"
        assert extract_agency_code_from_url("https://example.com/123456/page") == "123456"

    def test_query_param_muni(self):
        assert extract_agency_code_from_url("https://example.com?muni=123456") == "123456"

    def test_query_param_code(self):
        assert extract_agency_code_from_url("https://example.com?code=123456") == "123456"

    def test_no_match(self):
        assert extract_agency_code_from_url("https://example.com/page") is None

    def test_first_match_priority(self):
        # 複数マッチする場合、最初のパターンが優先
        url = "https://example.com/111111/?muni=222222"
        assert extract_agency_code_from_url(url) == "111111"


class TestIsPdfUrl:
    """is_pdf_url のテスト。"""

    def test_empty_url(self):
        assert is_pdf_url("") is False
        assert is_pdf_url(None) is False

    def test_pdf_extension(self):
        assert is_pdf_url("https://example.com/document.pdf") is True
        assert is_pdf_url("https://example.com/document.PDF") is True

    def test_pdf_with_query(self):
        assert is_pdf_url("https://example.com/document.pdf?download=1") is True

    def test_non_pdf(self):
        assert is_pdf_url("https://example.com/document.html") is False
        assert is_pdf_url("https://example.com/document.doc") is False


class TestMatchForecastPattern:
    """match_forecast_pattern のテスト。"""

    def test_empty_url(self):
        assert match_forecast_pattern("") is None
        assert match_forecast_pattern(None) is None

    def test_match(self):
        mock_patterns = [
            {"name": "group1", "keywords": ["yotei"], "priority": 1},
            {"name": "group2", "keywords": ["forecast"], "priority": 2},
        ]
        with patch("crawler.utils.forecast_url_detector.FORECAST_URL_PATTERNS", mock_patterns):
            result = match_forecast_pattern("https://example.com/yotei.html")
            assert result is not None
            assert result["name"] == "group1"
            assert result["matched_keyword"] == "yotei"
            assert result["priority"] == 1

    def test_no_match(self):
        with patch("crawler.utils.forecast_url_detector.FORECAST_URL_PATTERNS", 
                   [{"name": "group1", "keywords": ["yotei"], "priority": 1}]):
            assert match_forecast_pattern("https://example.com/other.html") is None

    def test_first_match_priority(self):
        mock_patterns = [
            {"name": "group1", "keywords": ["yotei"], "priority": 1},
            {"name": "group2", "keywords": ["yotei", "forecast"], "priority": 2},
        ]
        with patch("crawler.utils.forecast_url_detector.FORECAST_URL_PATTERNS", mock_patterns):
            result = match_forecast_pattern("https://example.com/yotei.html")
            # 最初にマッチしたグループが返される
            assert result["name"] == "group1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])