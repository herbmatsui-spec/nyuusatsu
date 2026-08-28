import sys
sys.path.insert(0, 'I:/入札システム')

from services.crawl_scheduler import CrawlScheduler

print("Starting Hokkaido pilot crawl...")
scheduler = CrawlScheduler()
result = scheduler.run_hokkaido_pilot()

print(f"\n=== Results ===")
print(f"Prefecture ID: {result.prefecture_id}")
print(f"Found: {result.bids_found}")
print(f"New: {result.bids_new}")
print(f"Updated: {result.bids_updated}")
if result.errors:
    print(f"Errors: {result.errors}")
print(f"Log: {result.log}")