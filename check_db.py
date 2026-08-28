import sys
sys.path.insert(0, 'D:/入札システム')
from database.session import get_db
from database.models import Prefecture, BidSource

with get_db() as db:
    count = db.query(Prefecture).count()
    print(f"Prefectures count: {count}")
    
    # BidSources count
    source_count = db.query(BidSource).count()
    print(f"BidSources count: {source_count}")
    
    # Hokkaido check
    hokkaido = db.query(Prefecture).filter_by(code='JP-01').first()
    if hokkaido:
        hk_sources = db.query(BidSource).filter_by(prefecture_id=hokkaido.id).count()
        print(f"Hokkaido ID={hokkaido.id}, Sources={hk_sources}")
    else:
        print("Hokkaido not found")