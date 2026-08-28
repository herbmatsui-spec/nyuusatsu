"""
Phase 06: ページネーション
Step 40: 最大ページ数を推定できるか確認
"""
import pytest
import asyncio


@pytest.mark.asyncio
async def test_get_max_pages_returns_int(live_geps_url):
    """get_max_pages() が int 型を返すことを確認"""
    from geps_crawler import GEPSCrawler
    from playwright.async_api import async_playwright
    from crawler.geps_crawler import CrawlerConfig
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    crawler = GEPSCrawler(CrawlerConfig())
    await crawler.init_browser()
    max_pages = crawler.get_max_pages(page)
    assert isinstance(max_pages, int)
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_max_pages_at_least_1(live_geps_url):
    """戻り値が 1 以上であることを確認"""
    from geps_crawler import GEPSCrawler
    from playwright.async_api import async_playwright
    from crawler.geps_crawler import CrawlerConfig
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    crawler = GEPSCrawler(CrawlerConfig())
    await crawler.init_browser()
    max_pages = crawler.get_max_pages(page)
    assert max_pages >= 1
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_max_pages_reasonable(live_geps_url):
    """戻り値が異常に大きくないことを確認（100以下）"""
    from geps_crawler import GEPSCrawler
    from playwright.async_api import async_playwright
    from crawler.geps_crawler import CrawlerConfig
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    crawler = GEPSCrawler(CrawlerConfig())
    await crawler.init_browser()
    max_pages = crawler.get_max_pages(page)
    assert max_pages <= 100
    await context.close()
    await browser.close()
    await pw.stop()