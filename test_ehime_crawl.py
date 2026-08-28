import asyncio
import os
import sys

# パス設定
sys.path.append("i:/入札システム")

from crawler.generic_crawler import GenericCrawler

async def test_crawl():
    # APIキーが必要な場合は環境変数から取得
    crawler = GenericCrawler(parser_type="agency_specific")
    # 愛媛県のURL
    print("Starting crawl...")
    results = await crawler.crawl_site("https://www.pref.ehime.jp/", "愛媛県")
    print(f"Found {len(results)} links")
    for r in results:
        print(f"Title: {r.title}, URL: {r.url}")

if __name__ == "__main__":
    asyncio.run(test_crawl())
