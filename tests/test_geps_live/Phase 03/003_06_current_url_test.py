import pytest
import asyncio

@pytest.mark.asyncio
async def test_current_url_after_navigation(live_geps_url):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until='domcontentloaded')
    url = page.url
    assert url
    assert url.startswith('https://')
    await context.close()
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_page_reload_preserves_url(live_geps_url):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until='domcontentloaded')
    url_before = page.url
    await page.reload()
    url_after = page.url
    assert url_before.rstrip('/') == url_after.rstrip('/')
    await context.close()
    await browser.close()
    await pw.stop()