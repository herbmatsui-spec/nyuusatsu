import asyncio
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from crawler.generic_crawler import GenericCrawler
from crawler.parsers.agency_config_loader import AgencyConfigLoader

AGENCIES = ["松山市", "今治市", "宇和島市"]

async def main():
    # parser_type="agency_specific" で動作を確認
    c = GenericCrawler(parser_type="agency_specific")
    loader = AgencyConfigLoader()
    
    for name in AGENCIES:
        cfg = loader.load(name)
        url = cfg.get("entry_url")
        if not url:
            print(f"[{name}] No entry_url found in config")
            continue
            
        print(f"Testing {name} with URL: {url}")
        try:
            results = await c.crawl_site(url, name)
            print(f"  -> Found {len(results)} results")
        except Exception as e:
            print(f"  -> Error crawling {name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
