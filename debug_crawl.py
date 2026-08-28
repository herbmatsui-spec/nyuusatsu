import os
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath('scripts/crawl_hokkaido.py')))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database.engine import SessionLocal
from database.models import Prefecture, Bid
from scripts.seed_prefectures import create_tables, seed_prefectures, seed_hokkaido_sources
from services.crawl_scheduler import CrawlScheduler

HOKKAIDO_LIST_FIXTURE = '''
<html><body>
  <h1>北海道 入札公告</h1>
  <ul>
    <li><a href="/dc/kim/nyusatsu/2026/it_system.html">【入札公告】令和8年度 情報システム保守委託（予算1,500万円）</a></li>
    <li><a href="/dc/kim/nyusatsu/2026/road_repair.html">【入札公告】令和8年度 道路補修工事（予算8,000万円）</a></li>
    <li><a href="/dc/kim/nyusatsu/2026/cleaning.html">【入札公告】令和8年度 庁舎清掃業務（予算300万円）</a></li>
    <li><a href="/dc/kim/nyusatsu/2026/spec.pdf">仕様書(PDF)</a></li>
  </ul>
</body></html>
'''

create_tables()
session = SessionLocal()
try:
    seed_prefectures(session)
    seed_hokkaido_sources(session)
finally:
    session.close()

scheduler = CrawlScheduler()
result = scheduler.run_hokkaido_pilot(html=HOKKAIDO_LIST_FIXTURE)

session = SessionLocal()
try:
    total_bids = session.query(Bid).count()
    print(f'total bids in DB: {total_bids}')
    all_bids = session.query(Bid).all()
    for bid in all_bids:
        print(f'  Bid: {bid.filename[:50]} | source_url: {bid.source_url} | prefecture_code: {bid.prefecture_code}')
finally:
    session.close()

print(f'found: {result.bids_found}, new: {result.bids_new}, updated: {result.bids_updated}')
print(f'errors: {result.errors}')