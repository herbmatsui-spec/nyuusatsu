import pytest
import asyncio

@pytest.mark.asyncio
async def test_playwright_launches():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    assert pw is not None
    await pw.stop()

@pytest.mark.asyncio
async def test_chromium_launches_headless():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    assert browser is not None
    await browser.close()
    await pw.stop()

@pytest.mark.asyncio
async def test_chromium_version_available():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    assert browser.version
    await browser.close()
    await pw.stop()