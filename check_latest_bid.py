import sys
sys.path.insert(0, 'D:/入札システム')
from database.session import get_db
from database.models import Bid

with get_db() as db:
    b = db.query(Bid).order_by(Bid.id.desc()).first()
    if b:
        print(f'Latest bid: id={b.id}, filename={b.filename}, status={b.current_status}, created={b.created_at}')
    else:
        print('No bids found')