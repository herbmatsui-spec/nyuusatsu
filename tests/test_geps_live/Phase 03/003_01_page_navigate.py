import pytest
import asyncio
from pathlib import Path

@pytest.mark.asyncio
async def test_navigate_to_geps(live_geps_url):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until='domcontentloaded')
    assert page.url
    await context.close()
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_page_title_not_empty(live_geps_url):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until='domcontentloaded')
    title = await page.title()
    assert len(title) > 0
    await context.close()
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_html_element_present(live_geps_url):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until='domcontentloaded')
    html = await page.query_selector('html')
    assert html is not None
    await context.close()
    await browser.close()
    await pw.stop()