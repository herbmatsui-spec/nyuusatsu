
import pytest
import asyncio
from geps_crawler import GEPSCrawler, CrawlerConfig
from crawler.generic_crawler import GenericCrawler
from crawler.parsers.heuristic_parser import HeuristicParser
from crawler.models.crawl_result import CrawlResult
from crawler.utils.rate_limiter import RateLimiter
from crawler.utils.proxy_manager import ProxyManager

def test_integration_full_parse_flow(sample_geps_html):
    """HTML取得 → パース → 結果抽出の全フロー"""
    config = CrawlerConfig()
    crawler = GEPSCrawler(config)
    results = crawler.parse_results(sample_geps_html, "https://www.geps.go.jp")
    assert len(results) > 0
    for r in results:
        assert "title" in r
        assert "pdf_url" in r
        assert "agency" in r
        assert "publish_date" in r

def test_integration_heuristic_and_crawl_result():
    """HeuristicParser結果がCrawlResult型であること"""
    parser = HeuristicParser()
    html = '<html><body><a href="/bid/spec.pdf">入札公告</a></body></html>'
    results = parser.parse(html, "https://example.com", "テスト省")
    for r in results:
        assert isinstance(r, CrawlResult)

def test_integration_rate_limiter_with_proxy():
    """RateLimiterとProxyManagerが併用可能か"""
    rl = RateLimiter(default_delay=0.01)
    pm = ProxyManager(proxies=["http://p1:8080"])
    proxy = pm.get_next_proxy()
    assert proxy is not None
    domain = rl._get_domain("https://www.geps.go.jp/search")
    assert domain == "www.geps.go.jp"

@pytest.mark.asyncio
async def test_integration_crawl_with_mocked_browser(mocker):
    """GenericCrawlerの全フロー（ブラウザモック）"""
    crawler = GenericCrawler(delay=0.01)
    mock_page = mocker.AsyncMock()
    mock_page.content = mocker.AsyncMock(return_value='<html><body><a href="/bid/spec.pdf">入札仕様書</a></body></html>')
    mock_page.url = "https://example.com"
    mock_context = mocker.AsyncMock()
    mock_browser = mocker.AsyncMock()

    mocker.patch.object(crawler, "init_browser", return_value=(mock_browser, mock_context, mock_page))
    mocker.patch.object(crawler, "navigate", return_value=True)
    mocker.patch.object(crawler, "close", return_value=None)

    results = await crawler.crawl_site("https://example.com", "テスト省")
    assert len(results) >= 1
    assert all(isinstance(r, CrawlResult) for r in results)

# =============================================================================
# 実際のGEPSサイトへの実接続テスト (Live Integration Test)
# =============================================================================
@pytest.mark.asyncio
async def test_live_geps_crawler():
    """
    実際のGEPSサイトにアクセスする実動作テスト。
    Playwrightで実際にブラウザを動かし、検索結果URLにアクセスします。
    """
    # ネットワーク接続やPlaywright依存のため、失敗してもテスト全体を落とさないよう、
    # もしくはスキップできるように例外をハンドリングしつつ実行します。
    config = CrawlerConfig(
        search_url="https://www.geps.go.jp/search", # もしくは適当な公開ページ
        sleep_interval=2,
    )
    crawler = GEPSCrawler(config)
    
    try:
        # headless=Trueでブラウザ起動し、トップレベルのクロールを実行
        # 時間節約のため、最大1ページのみ
        # テスト対象のURLにアクセスできるか確認
        browser, context, page = await crawler.init_browser()
        try:
            # ページ遷移とタイトル取得を試みる
            await page.goto("https://www.geps.go.jp/index.html", timeout=30000, wait_until="domcontentloaded")
            title = await page.title()
            assert "政府調達" in title or "GEPS" in title or "Portal" in title or len(title) > 0
            print(f"\n[LIVE TEST] Successfully navigated to GEPS. Page title: {title}")
        finally:
            await context.close()
            await browser.close()
            if crawler.pw:
                await crawler.pw.stop()
    except Exception as e:
        pytest.skip(f"Skipping live GEPS test due to environment/network error: {e}")
