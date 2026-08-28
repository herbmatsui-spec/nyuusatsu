import sys
sys.path.insert(0, 'D:/入札システム')
from database.session import get_db
from database.models import Bid

with get_db() as db:
    count = db.query(Bid).count()
    print(f'Total bids: {count}')
    
    latest = db.query(Bid).order_by(Bid.id.desc()).limit(5).all()
    for bid in latest:
        print(f'  - id={bid.id}, filename={bid.filename}, source_url={bid.source_url}, status={bid.current_status}')