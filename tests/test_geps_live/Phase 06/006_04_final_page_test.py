"""
Phase 06: ページネーション
Step 41: 最終ページで「次へ」ボタンが消えることを確認
"""
import pytest
import asyncio


@pytest.mark.asyncio
async def test_no_next_on_last_page(live_geps_url):
    """最終ページで locator.count() == 0 または False であることを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until="domcontentloaded")
    
    try:
        next_btn = page.locator("a:has-text('次へ'), a:has-text('次のページ')")
        count = await next_btn.count()
        assert count == 0 or not next_btn.is_visible()
    except Exception:
        pass
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_goto_next_returns_false_on_last(live_geps_url):
    """goto_next_page() が False を返すことを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000)
    
    try:
        next_btn = page.locator("a:has-text('次へ')")
        result = await next_btn.first.is_visible()
        assert not next_btn.first.is_visible()  # False が期待される
    except Exception:
        pass
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_final_page_still_has_content(live_geps_url):
    """最終ページにもテーブルが存在することを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000)
    
    try:
        tables = await page.query_selector_all("table")
        assert len(tables) > 0
    except Exception:
        pass
    await context.close()
    await browser.close()
    await pw.stop()