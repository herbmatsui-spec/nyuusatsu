import sys
sys.path.append('D:/入札システム')
from database.session import get_db
from database.models.agency_category import AgencyCategory
with get_db() as session:
    cats = session.query(AgencyCategory).all()
    for c in cats:
        print(c.id, c.name)
