"""市区町村向け発注機関クローラ

- `AgencyListFetcher` を継承
- `config.municipality_sources.MUNICIPALITY_SOURCES` に各自治体の URL が登録されていることを前提とする
- `fetch_and_store` は対象都道府県内の全市区町村を巡回し、`AgencyInventory` に upsert
"""

from crawler.agency_list_fetcher import AgencyListFetcher
from config.municipality_sources import MUNICIPALITY_SOURCES
from config.prefectures import PREFECTURES
from database.engine import engine
from database.models.agency_inventory import AgencyInventory
from sqlalchemy.orm import Session

class MunicipalityFetcher(AgencyListFetcher):
    def __init__(self, timeout: int = 15):
        super().__init__(timeout=timeout)

    def fetch_and_store(self, prefecture_code: str):
        prefecture_name = PREFECTURES.get(prefecture_code, "")
        municipalities = MUNICIPALITY_SOURCES.get(prefecture_name, {})
        if not municipalities:
            raise ValueError(f"No municipality source data for {prefecture_name}")
        with Session(engine) as sess:
            for muni_name, url in municipalities.items():
                html = self.fetch_top_page(url)
                links = self.find_bid_links(html)
                bid_url = None
                for l in links:
                    if "bid" in l.lower() or "入札" in l:
                        bid_url = l if l.startswith("http") else url.rstrip('/') + '/' + l.lstrip('/')
                        break
                inv = sess.query(AgencyInventory).filter_by(
                    prefecture_code=prefecture_code,
                    municipality=muni_name,
                ).first()
                if inv:
                    inv.top_page_url = url
                    inv.bid_page_url = bid_url
                    inv.page_format = "html"
                    inv.is_crawled = False
                else:
                    inv = AgencyInventory(
                        agency_name=muni_name,
                        prefecture_code=prefecture_code,
                        municipality=muni_name,
                        top_page_url=url,
                        bid_page_url=bid_url,
                        page_format="html",
                        is_crawled=False,
                    )
                    sess.add(inv)
            sess.commit()
