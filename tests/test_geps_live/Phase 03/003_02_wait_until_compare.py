import pytest
import asyncio
import time

@pytest.mark.asyncio
async def test_domcontentloaded_faster_than_networkidle(live_geps_url):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    t0 = time.time()
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until='domcontentloaded')
    t1 = time.time()
    await context.close()
    assert (t1 - t0) < 30
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_load_works(live_geps_url):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until='load')
    content = await page.content()
    assert len(content) > 0
    await context.close()
    await browser.close()
    await pw.stop()