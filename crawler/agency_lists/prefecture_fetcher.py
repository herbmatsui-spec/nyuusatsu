"""都道府県庁向け発注機関クローラ

- `AgencyListFetcher` を継承
- 各都道府県のトップページ URL は `config/agency_sources.py` の `AGENCY_SOURCES` から取得
- `fetch_and_store` でリンク抽出後、`AgencyInventory` に upsert
"""

from crawler.agency_list_fetcher import AgencyListFetcher
from config.agency_sources import AGENCY_SOURCES
from config.prefectures import PREFECTURES
from database.engine import engine
from database.models.agency_inventory import AgencyInventory
from sqlalchemy.orm import Session

class PrefectureFetcher(AgencyListFetcher):
    def __init__(self, timeout: int = 15):
        super().__init__(timeout=timeout)

    def fetch_and_store(self, prefecture_code: str):
        prefecture_name = PREFECTURES.get(prefecture_code, "")
        base_url = AGENCY_SOURCES.get(prefecture_name)
        if not base_url:
            raise ValueError(f"No agency source URL for {prefecture_name}")
        html = self.fetch_top_page(base_url)
        links = self.find_bid_links(html)
        # Simple heuristic: first link containing 'bid' or 'tender'
        bid_url = None
        for l in links:
            if "bid" in l.lower() or "入札" in l:
                bid_url = l if l.startswith("http") else base_url.rstrip('/') + '/' + l.lstrip('/')
                break
        # Store to DB
        with Session(engine) as sess:
            inv = sess.query(AgencyInventory).filter_by(prefecture_code=prefecture_code, agency_name=prefecture_name).first()
            if inv:
                inv.top_page_url = base_url
                inv.bid_page_url = bid_url
                inv.page_format = "html"
                inv.is_crawled = False
            else:
                inv = AgencyInventory(
                    agency_name=prefecture_name,
                    prefecture_code=prefecture_code,
                    top_page_url=base_url,
                    bid_page_url=bid_url,
                    page_format="html",
                    is_crawled=False,
                )
                sess.add(inv)
            sess.commit()
        return bid_url
