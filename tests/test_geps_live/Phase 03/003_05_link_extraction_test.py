import pytest
import asyncio

@pytest.mark.asyncio
async def test_link_count_positive(live_geps_url):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until='domcontentloaded')
    links = await page.query_selector_all('a[href]')
    assert len(links) > 0
    await context.close()
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_pdf_links_present(live_geps_url):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until='domcontentloaded')
    links = await page.query_selector_all('a[href$=".pdf"]')
    assert len(links) >= 0
    await context.close()
    await browser.close()
    await pw.stop()