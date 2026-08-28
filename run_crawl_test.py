import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.crawl_scheduler import CrawlScheduler

if __name__ == "__main__":
    scheduler = CrawlScheduler()
    print("Starting Hokkaido pilot crawl...")
    result = scheduler.run_hokkaido_pilot()
    print(f"Results: Found={result.bids_found}, New={result.bids_new}, Updated={result.bids_updated}")
    if result.errors:
        print(f"Errors: {result.errors}")
    print(f"Log: {result.log}")