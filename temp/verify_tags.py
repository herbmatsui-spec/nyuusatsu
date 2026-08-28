import sys
sys.path.append('D:/入札システム')
from database.session import get_db
from database.models.agency import Agency
with get_db() as session:
    total = session.query(Agency).count()
    # Count by system_type via grouping not directly available, just show sample
    sample = session.query(Agency).filter(Agency.system_type.isnot(None)).limit(10).all()
    for a in sample:
        print(a.id, a.name, a.system_type)
    print('Total:', total)
