import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("A: import get_db", flush=True)
from database.session import get_db
print("B: done", flush=True)

with get_db() as db:
    print("C: opened db", flush=True)
    from database.models import Prefecture
    print("D: imported Prefecture", flush=True)
    p = db.query(Prefecture).filter_by(code="JP-01").first()
    print("E: queried", p.id if p else None, flush=True)