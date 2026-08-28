import pytest
import asyncio

@pytest.mark.asyncio
async def test_page_created_from_context():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    assert page is not None
    await context.close()
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_page_default_timeout_settable():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    page.set_default_timeout(10000)
    await context.close()
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_page_content_accessible():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto('data:text/html,<html><body>hello</body></html>')
    content = await page.content()
    assert 'hello' in content
    await context.close()
    await browser.close()
    await pw.stop()