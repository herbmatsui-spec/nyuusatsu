import csv
import datetime
import logging
from typing import List
from sqlalchemy.orm import Session
from database.base import Base
from database.models.agency import Agency
from database.models.agency_category import AgencyCategory
from database.session import get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def import_ministries(csv_path: str):
    """省政府庁マスタCSVをDBに投入する"""
    try:
        with get_session() as session:
            # カテゴリ「国」のIDを取得
            category = session.query(AgencyCategory).filter_by(name="国").first()
            if not category:
                logger.error("Category '国' not found. Please run scripts/init_categories.py first.")
                return

            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    # 既存チェック
                     exists = session.query(Agency).filter(
                         Agency.name == row['agency_name'],
                         Agency.municipality_code == row['municipality_code']
                     ).first()

                     if not exists:
                         agency = Agency(
                             name=row['agency_name'],
                             municipality_code=row['municipality_code'],
                             category_id=category.id,
                             priority_level=int(row['priority_level']),
                             created_at=datetime.datetime.now(),
                             updated_at=datetime.datetime.now()
                         )
                         session.add(agency)
                         count += 1
                
                session.commit()
                logger.info(f"Successfully imported {count} ministries from {csv_path}")
    except Exception as e:
        logger.error(f"Failed to import ministries: {e}")

if __name__ == "__main__":
    import_ministries("data/master_ministries.csv")
