import sys
sys.path.append('D:/入札システム')
import csv
import logging
from database.session import get_db
from database.models.agency import Agency

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def detect_missing_agencies():
    with get_db() as session:
        registered_codes = set(
            a[0] for a in session.query(Agency.municipality_code).filter(Agency.municipality_code.isnot(None)).all()
        )
        registered_names = set(
            a[0] for a in session.query(Agency.name).all()
        )
    missing = []
    with open('data/agencies.csv', mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get('municipality_code')
            name = row.get('name')
            missing_code = code and code not in registered_codes
            missing_name = name and name not in registered_names
            if missing_code or missing_name:
                missing.append(row)
    logger.info(f"Missing agencies count: {len(missing)}")
    for m in missing[:10]:
        logger.info(f"  - {m.get('name')} ({m.get('municipality_code')})")
    if missing:
        with open('data/missing_agencies.csv', mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=missing[0].keys())
            writer.writeheader()
            writer.writerows(missing)
        logger.info("Saved missing agencies to data/missing_agencies.csv")

if __name__ == '__main__':
    detect_missing_agencies()
