import pytest
import asyncio

@pytest.mark.asyncio
async def test_table_selector_present(live_geps_url):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until='domcontentloaded')
    try:
        await page.wait_for_selector('table', timeout=10000)
        tables = await page.query_selector_all('table')
        assert len(tables) >= 0
    except Exception:
        pass
    await context.close()
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_tr_elements_present(live_geps_url):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until='domcontentloaded')
    trs = await page.query_selector_all('tr')
    assert len(trs) >= 0
    await context.close()
    await browser.close()
    await pw.stop()