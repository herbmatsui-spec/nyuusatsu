"""Tests for Agency URL Templates utility."""

import pytest
from crawler.utils.agency_url_templates import (
    AGENCY_URL_TEMPLATES,
    get_templates_for_type,
    get_forecast_url_candidates,
)


class TestAgencyUrlTemplates:
    """agency_url_templates のテスト。"""

    def test_templates_structure(self):
        """テンプレート構造の確認"""
        assert len(AGENCY_URL_TEMPLATES) == 2
        
        # municipality
        mun = AGENCY_URL_TEMPLATES[0]
        assert mun["agency_type"] == "municipality"
        assert len(mun["templates"]) == 5
        assert "/yotei.html" in mun["templates"]
        assert "/index.html?page=forecast" in mun["templates"]
        assert "発注見通し" in mun["keyword_hints"]
        
        # prefecture
        pref = AGENCY_URL_TEMPLATES[1]
        assert pref["agency_type"] == "prefecture"
        assert len(pref["templates"]) == 3
        assert "/bid/forecast/" in pref["templates"]
        assert "年度発注見通し" in pref["keyword_hints"]

    def test_get_templates_for_type_municipality(self):
        """市区町村タイプのテンプレート取得"""
        templates = get_templates_for_type("municipality")
        
        assert len(templates) == 5
        assert templates == [
            "/yotei.html",
            "/index.html?page=forecast",
            "/info/forecast.html",
            "/procurement/plan.html",
            "/shisetsu/yotei.html",
        ]

    def test_get_templates_for_type_prefecture(self):
        """都道府県タイプのテンプレート取得"""
        templates = get_templates_for_type("prefecture")
        
        assert len(templates) == 3
        assert templates == [
            "/bid/forecast/",
            "/contract/plan/",
            "/yotei/index.html",
        ]

    def test_get_templates_for_type_unknown(self):
        """未知のタイプ"""
        templates = get_templates_for_type("unknown")
        assert templates == []

    def test_get_forecast_url_candidates_municipality(self):
        """市区町村のURL候補生成"""
        base_url = "https://example.city.jp"
        urls = get_forecast_url_candidates(base_url, "municipality")
        
        assert len(urls) == 5
        assert urls == [
            "https://example.city.jp/yotei.html",
            "https://example.city.jp/index.html?page=forecast",
            "https://example.city.jp/info/forecast.html",
            "https://example.city.jp/procurement/plan.html",
            "https://example.city.jp/shisetsu/yotei.html",
        ]

    def test_get_forecast_url_candidates_prefecture(self):
        """都道府県のURL候補生成"""
        base_url = "https://pref.example.jp"
        urls = get_forecast_url_candidates(base_url, "prefecture")
        
        assert len(urls) == 3
        assert urls == [
            "https://pref.example.jp/bid/forecast/",
            "https://pref.example.jp/contract/plan/",
            "https://pref.example.jp/yotei/index.html",
        ]

    def test_get_forecast_url_candidates_base_url_trailing_slash(self):
        """ベースURLに末尾スラッシュがある場合"""
        base_url = "https://example.city.jp/"
        urls = get_forecast_url_candidates(base_url, "municipality")
        
        # 末尾スラッシュが除去されて結合される
        assert urls[0] == "https://example.city.jp/yotei.html"

    def test_get_forecast_url_candidates_default_type(self):
        """デフォルトタイプ（municipality）"""
        base_url = "https://example.city.jp"
        urls = get_forecast_url_candidates(base_url)
        
        assert len(urls) == 5
        assert urls[0] == "https://example.city.jp/yotei.html"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])