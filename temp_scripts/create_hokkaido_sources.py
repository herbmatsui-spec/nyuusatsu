import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import get_db
from database.models import BidSource, Prefecture

def seed():
    with get_db() as db:
        hokkaido = db.query(Prefecture).filter_by(code='JP-01').first()
        if not hokkaido:
            print("Error: Hokkaido not found")
            return

        sources = [
            BidSource(
                prefecture_id=hokkaido.id,
                source_type="web",
                url="https://www.pref.hokkaido.lg.jp/",
                parser_type="heuristic",
                crawl_interval_hours=24,
                is_active=True,
                notes="Hokkaido official site",
            ),
            BidSource(
                prefecture_id=hokkaido.id,
                source_type="geps",
                url="https://search.geps.go.jp/search?q=%E5%8C%97%E6%B5%B7%E9%81%93&pref=01",
                parser_type="agency_specific",
                crawl_interval_hours=24,
                is_active=True,
                notes="GEPS Hokkaido",
            ),
        ]

        for src in sources:
            existing = db.query(BidSource).filter_by(url=src.url).first()
            if not existing:
                db.add(src)
                print(f"Added: {src.url}")
        
        db.commit()
        count = db.query(BidSource).filter_by(prefecture_id=hokkaido.id).count()
        print(f"Done. Hokkaido sources: {count}")

if __name__ == "__main__":
    seed()