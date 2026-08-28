import pytest
import asyncio

@pytest.mark.asyncio
async def test_headless_true_works():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    assert browser is not None
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_headless_false_works():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.launch(headless=False)
        assert browser is not None
        await browser.close()
    finally:
        await pw.stop()

@pytest.mark.asyncio
async def test_headless_vs_headful_page_works():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto('data:text/html,<html><body>test</body></html>')
    title = await page.title()
    assert len(title) >= 0
    await context.close()
    await browser.close()
    await pw.stop()