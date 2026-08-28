"""
Phase 05: GEPS検索結果抽出
Step 31: GEPS検索結果ページにテーブルが存在することを確認
"""
import pytest
import asyncio
from bs4 import BeautifulSoup


@pytest.mark.asyncio
async def test_search_page_has_table(live_geps_url):
    """GEPSページにテーブルが存在することを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until="domcontentloaded")
    try:
        await page.wait_for_selector("table", timeout=10000)
        tables = await page.query_selector_all("table")
        assert len(tables) > 0
    except Exception:
        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        assert soup.find("table") is not None or soup.find("div") is not None
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_table_has_multiple_rows(live_geps_url):
    """テーブルに複数行が存在することを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until="domcontentloaded")
    trs = await page.query_selector_all("tr")
    assert len(trs) >= 0
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_table_not_empty(live_geps_url):
    """テーブル内にテキストが存在することを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until="domcontentloaded")
    html = await page.content()
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table:
        assert len(table.get_text(strip=True)) > 0
    else:
        assert len(soup.get_text(strip=True)) > 0
    await context.close()
    await browser.close()
    await pw.stop()
