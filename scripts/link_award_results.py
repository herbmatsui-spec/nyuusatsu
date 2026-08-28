import asyncio
import logging
from geps_crawler import GEPSCrawler, CrawlerConfig
from services.award_result_service import AwardResultService

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # 落札結果ページのURL（仮）
    award_url = "https://www.geps.go.jp/award_results" 
    
    crawler = GEPSCrawler(CrawlerConfig(search_url=award_url))
    service = AwardResultService()
    
    print("Crawling award results...")
    results = await crawler.crawl(award_url, max_pages=1, is_award=True)
    
    print(f"Found {len(results)} awards. Linking...")
    for award in results:
        try:
            service.link_award_to_bid(award)
            print(f"Linked: {award['title']}")
        except Exception as e:
            print(f"Failed to link {award['title']}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
