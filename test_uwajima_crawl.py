import asyncio
import sys
import os
from playwright.async_api import async_playwright

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

async def main():
    print("宇和島市の入札関連ページを調査します...")
    target_urls = [
        "https://www.city.uwajima.ehime.jp/site/koujisub/",
        "https://www.city.uwajima.ehime.jp/soshiki/50/index-2.html"
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for url in target_urls:
            print(f"Crawling: {url}")
            await page.goto(url)
            links = await page.query_selector_all("a")
            for link in links:
                href = await link.get_attribute("href")
                if href and href.lower().endswith(".pdf"):
                    print(f"PDF Found: {href}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
