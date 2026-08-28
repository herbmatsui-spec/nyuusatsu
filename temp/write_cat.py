import sys
sys.path.append('D:/入札システム')
from database.session import get_db
from database.models.agency_category import AgencyCategory
with get_db() as session:
    cats = session.query(AgencyCategory).all()
    with open('D:/入札システム/temp/cat_utf8.txt', 'w', encoding='utf-8') as f:
        for c in cats:
            f.write(f"{c.id}\t{c.name}\n")
    print("written")
