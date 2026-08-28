import os
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath('scripts/crawl_hokkaido.py')))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crawler.hokkaido.scanner import HokkaidoCrawler

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

crawler = HokkaidoCrawler()
bids_data = crawler.parse(HOKKAIDO_LIST_FIXTURE, "https://www.pref.hokkaido.lg.jp")

for bid in bids_data:
    print(f"title: {bid.get('title')}")
    print(f"url: {bid.get('url')}")
    print(f"text: {bid.get('text')}")
    print("---")