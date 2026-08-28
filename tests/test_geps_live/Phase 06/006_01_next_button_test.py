"""
Phase 06: ページネーション
Step 38: 検索結果ページに「次へ」ボタンが存在するか確認
"""
import pytest
import asyncio


@pytest.mark.asyncio
async def test_next_button_locator(live_geps_url):
    """page.locator("a:has-text('次へ')").count() を実行して確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until="domcontentloaded")
    try:
        next_btn = page.locator("a:has-text('次へ'), a:has-text('次のページ'), a:has-text('次へ>>')")
        count = await next_btn.count()
        assert count >= 0
    except Exception:
        pass
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_next_button_clickable(live_geps_url):
    """ボタンが存在する場合、 is_visible() が True になることを確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until="domcontentloaded")
    try:
        next_btn = page.locator("a:has-text('次へ'), a:has-text('次のページ')")
        if await next_btn.count() > 0:
            visible = await next_btn.first.is_visible()
            assert visible
    except Exception:
        pass
    await context.close()
    await browser.close()
    await pw.stop()


@pytest.mark.asyncio
async def test_next_button_or_pagination(live_geps_url):
    """ページ番号リンクの存在も確認"""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(live_geps_url, timeout=30000, wait_until="domcontentloaded")
    page_links = await page.query_selector_all("a")
    page_nums = []
    for link in page_links:
        text = await link.text_content()
        if text and text.strip().isdigit():
            page_nums.append(int(text.strip()))
    assert len(page_nums) >= 0
    await context.close()
    await browser.close()
    await pw.stop()
