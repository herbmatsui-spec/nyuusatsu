import pytest
import asyncio

@pytest.mark.asyncio
async def test_context_close_cleanly():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    await context.close()
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_multiple_pages_then_close():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    p1 = await context.new_page()
    p2 = await context.new_page()
    await p1.close()
    await p2.close()
    await context.close()
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_playwright_stop_after_close():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    await context.close()
    await browser.close()
    await pw.stop()