"""
Phase 03: ナビゲーション
Step 30: Playwrightで取得したページコンテンツがBeautifulSoupでパース可能であることを確認
"""
import pytest
import asyncio
from bs4 import BeautifulSoup


@pytest.mark.asyncio
async def test_page_content_parseable(live_geps_url):
    """ページコンテンツがBeautifulSoupでパース可能であることを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until="domcontentloaded")
    html = await page.content()
    soup = BeautifulSoup(html, "lxml")
    assert soup is not None
    assert soup.find("html") is not None
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_page_content_has_table_or_div(live_geps_url):
    """パース結果に table または div が含まれることを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until="domcontentloaded")
    html = await page.content()
    soup = BeautifulSoup(html, "lxml")
    has_table = soup.find("table") is not None
    has_div = soup.find("div") is not None
    assert has_table or has_div
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_page_content_links_extractable(live_geps_url):
    """パース結果からリンクが抽出可能であることを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until="domcontentloaded")
    html = await page.content()
    soup = BeautifulSoup(html, "lxml")
    links = soup.find_all("a", href=True)
    assert len(links) > 0
    await context.close()
    await browser.close()
    await pw.stop()
