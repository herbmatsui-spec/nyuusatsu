import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import get_db
from database.models import BidSource, Prefecture

with get_db() as db:
    count = db.query(BidSource).count()
    print(f"Total BidSources: {count}")
    
    hokkaido = db.query(Prefecture).filter_by(code='JP-01').first()
    if hokkaido:
        hk_count = db.query(BidSource).filter_by(prefecture_id=hokkaido.id).count()
        print(f"Hokkaido ID={hokkaido.id}, Sources={hk_count}")
    else:
        print("Hokkaido not found")