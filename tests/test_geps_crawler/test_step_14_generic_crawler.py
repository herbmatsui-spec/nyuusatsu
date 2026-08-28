from crawler.generic_crawler import GenericCrawler
from crawler.models.crawl_result import CrawlResult
import pytest

def test_generic_crawler_init():
    """GenericCrawlerの初期化"""
    crawler = GenericCrawler()
    assert crawler.parser_type == "heuristic"
    assert crawler.max_depth == 2
    assert len(crawler.visited_urls) == 0

def test_generic_crawler_custom_init():
    """カスタムパラメータでの初期化"""
    crawler = GenericCrawler(parser_type="rss", delay=1.0, max_depth=5)
    assert crawler.parser_type == "rss"
    assert crawler.max_depth == 5

def test_generic_crawler_visited_urls():
    """訪問済みURL管理"""
    crawler = GenericCrawler()
    url = "https://example.com/page1"
    assert not crawler._has_been_visited(url)
    crawler._mark_as_visited(url)
    assert crawler._has_been_visited(url)

def test_generic_crawler_normalize_url():
    """URL正規化テスト"""
    crawler = GenericCrawler()
    assert crawler._normalize_url("https://example.com/page#section") == "https://example.com/page"
    assert crawler._normalize_url("https://example.com/path/") == "https://example.com/path"

def test_generic_crawler_depth_limit():
    """深度制限の判定"""
    crawler = GenericCrawler(max_depth=3)
    assert crawler._is_depth_within_limit(0) == True
    assert crawler._is_depth_within_limit(3) == True
    assert crawler._is_depth_within_limit(4) == False

def test_generic_crawler_next_depth():
    """次の深度計算"""
    crawler = GenericCrawler()
    assert crawler._get_next_depth(0) == 1
    assert crawler._get_next_depth(2) == 3

@pytest.mark.asyncio
async def test_generic_crawler_extract_links_heuristic():
    """ヒューリスティックパーサーでリンク抽出"""
    crawler = GenericCrawler(parser_type="heuristic")
    html = '<html><body><a href="/bid/spec.pdf">入札仕様書</a></body></html>'
    results = await crawler.extract_links(html, "https://example.com", "テスト省")
    assert len(results) >= 1

@pytest.mark.asyncio
async def test_generic_crawler_extract_links_rss(sample_rss_xml):
    """RSSパーサーでリンク抽出"""
    crawler = GenericCrawler(parser_type="rss")
    results = await crawler.extract_links(sample_rss_xml, "https://example.gov.jp", "テスト省")
    assert len(results) == 2
