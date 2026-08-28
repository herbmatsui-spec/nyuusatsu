import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.session import get_db
from database.models import Bid, Prefecture, BidSource

print("Checking database...")

with get_db() as db:
    bid_count = db.query(Bid).count()
    pref_count = db.query(Prefecture).count()
    source_count = db.query(BidSource).count()
    
    hokkaido = db.query(Prefecture).filter_by(code='JP-01').first()
    hk_sources = 0
    if hokkaido:
        hk_sources = db.query(BidSource).filter_by(prefecture_id=hokkaido.id).count()

print("=== 現在の進捗状況 ===")
print(f"都道府県登録数: {pref_count}")
print(f"クロール対象ソース数: {source_count}")
print(f"北海道のクロール対象: {hk_sources}")
print(f"収集済み入札情報: {bid_count}件")
print("Done.")