import pytest
import asyncio

@pytest.mark.asyncio
async def test_context_created_with_defaults():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    assert context is not None
    await context.close()
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_context_with_custom_user_agent():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    ua = 'Mozilla/5.0 TestBrowser/1.0'
    context = await browser.new_context(user_agent=ua)
    page = await context.new_page()
    await page.goto('data:text/html,<html><body>test</body></html>')
    agent = await page.evaluate('() => navigator.userAgent')
    assert ua in agent
    await context.close()
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_context_ignore_https_errors():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(ignore_https_errors=True)
    assert context is not None
    await context.close()
    await browser.close()
    await pw.stop()