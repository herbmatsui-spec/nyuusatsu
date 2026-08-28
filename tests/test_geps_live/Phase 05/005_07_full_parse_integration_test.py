"""
Phase 05: GEPS検索結果抽出
Step 37: GEPSCrawler の parse_results() を使った完全パーサーの統合テスト
"""
import pytest
from geps_crawler import GEPSCrawler, CrawlerConfig


def test_parse_results_returns_list(sample_geps_html):
    """parse_results() の戻り値が list 型であることを確認"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_results(sample_geps_html, "https://www.geps.go.jp")
    assert isinstance(results, list)


def test_parse_results_dict_keys(sample_geps_html):
    """各要素に title, agency, pdf_url, publish_date キーが存在することを確認"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_results(sample_geps_html, "https://www.geps.go.jp")
    if results:
        required_keys = ["agency", "title", "pdf_url", "publish_date"]
        for key in required_keys:
            assert key in results[0]


def test_parse_results_count_matches(sample_geps_html):
    """抽出件数が期待値と一致することを確認"""
    crawler = GEPSCrawler(CrawlerConfig())
    results = crawler.parse_results(sample_geps_html, "https://www.geps.go.jp")
    assert len(results) == 2
