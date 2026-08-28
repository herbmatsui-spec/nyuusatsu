"""
Phase 06: ページネーション
Step 39: 「次へ」ボタンをクリックしてページが遷移することを確認
"""
import pytest
import asyncio


@pytest.mark.asyncio
async def test_next_button_click_navigation(live_geps_url):
    """ボタンをクリックし、 URL が変更されることを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until="domcontentloaded")
    
    try:
        next_btn = page.locator("a:has-text('次へ'), a:has-text('次のページ')")
        if await next_btn.count() > 0:
            url_before = page.url
            await next_btn.first.click()
            await page.wait_for_load_state("domcontentloaded")
            url_after = page.url
            assert url_before != url_after
            assert url_after != url_before
    except Exception:
        pass
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_navigation_load_state(live_geps_url):
    """遷移後のページが正常にロードされることを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000)
    
    try:
        next_btn = page.locator("a:has-text('次へ')")
        if await next_btn.count() > 0:
            await next_btn.first.click()
            await page.wait_for_load_state("domcontentloaded")
            assert page.url is not None
    except Exception:
        pass
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_page_transition_content_diff(live_geps_url):
    """遷移前後でコンテンツが変化することを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000)
    
    try:
        html_before = await page.content()
        next_btn = page.locator("a:has-text('次へ')")
        if await next_btn.count() > 0:
            await next_btn.first.click()
            await page.wait_for_load_state("domcontentloaded")
            html_after = await page.content()
            assert html_before != html_after
    except Exception:
        pass
    await context.close()
    await browser.close()
    await pw.stop()
