"""AgencyInventory 用リポジトリ

- `upsert` で機関名・都道府県コード・入札ページ URL を一意に登録
- `list_uncrawled` で未クロール機関一覧取得
- `mark_crawled` でクロール完了フラグを更新
"""

from sqlalchemy.orm import Session
from database.models.agency_inventory import AgencyInventory

class AgencyInventoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, agency_name: str, prefecture_code: str, bid_page_url: str | None = None, municipality: str | None = None):
        inv = self.session.query(AgencyInventory).filter_by(
            agency_name=agency_name,
            prefecture_code=prefecture_code,
            municipality=municipality,
        ).first()
        if inv:
            if bid_page_url:
                inv.bid_page_url = bid_page_url
            inv.is_crawled = False
        else:
            inv = AgencyInventory(
                agency_name=agency_name,
                prefecture_code=prefecture_code,
                municipality=municipality,
                bid_page_url=bid_page_url,
                page_format="html" if bid_page_url else "unknown",
                is_crawled=False,
            )
            self.session.add(inv)
        self.session.commit()
        return inv

    def list_uncrawled(self, limit: int = 100):
        return (
            self.session.query(AgencyInventory)
            .filter_by(is_crawled=False)
            .order_by(AgencyInventory.id)
            .limit(limit)
            .all()
        )

    def mark_crawled(self, agency_id: int):
        inv = self.session.query(AgencyInventory).filter_by(id=agency_id).first()
        if inv:
            inv.is_crawled = True
            self.session.commit()
        return inv
