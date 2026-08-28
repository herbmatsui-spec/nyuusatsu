import pytest
import asyncio

@pytest.mark.asyncio
async def test_error_on_invalid_executable_path():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    with pytest.raises(Exception):
        await pw.chromium.launch(executable_path='/nonexistent/path')
    await pw.stop()

@pytest.mark.asyncio
async def test_close_even_when_context_fails():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    try:
        context = await browser.new_context()
        await context.close()
    finally:
        await browser.close()
        await pw.stop()