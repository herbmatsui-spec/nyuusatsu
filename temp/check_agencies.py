import sys
sys.path.append('D:/入札システム')
from database.session import get_db
from database.models.agency import Agency
with get_db() as session:
    total = session.query(Agency).count()
    ministries = session.query(Agency).filter(Agency.category_id == 1).count()
    pref = session.query(Agency).filter(Agency.category_id == 2).count()
    munic = session.query(Agency).filter(Agency.category_id == 3).count()
    other = session.query(Agency).filter(Agency.category_id == 4).count()
    print(f"Total: {total}")
    print(f"Ministries(1): {ministries}")
    print(f"Prefs(2): {pref}")
    print(f"Municipalities(3): {munic}")
    print(f"Other(4): {other}")
