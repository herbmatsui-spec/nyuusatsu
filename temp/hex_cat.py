import sys
sys.path.append('D:/入札システム')
from database.session import get_db
with get_db() as session:
    rows = session.execute("SELECT id, printf('%02X', unicode(name)) FROM agency_categories").fetchall()
    for r in rows:
        print(r)
