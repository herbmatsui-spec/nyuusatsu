import sys
sys.path.append('D:/入札システム')
from database.session import get_db
from database.models.agency import Agency
with get_db() as session:
    agencies = session.query(Agency).all()
    for a in agencies:
        cat_name = a.category.name if a.category else 'None'
        print(f"{a.id}\t{a.name}\t{a.municipality_code}\t{cat_name}")
