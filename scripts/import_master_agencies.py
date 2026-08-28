import csv
import logging
from typing import List
from sqlalchemy.orm import Session
from database.base import Base
from database.models.agency import Agency
from database.models.agency_category import AgencyCategory
from database.session import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _get_existing_keys(session: Session):
    existing = session.query(Agency).all()
    names = set()
    codes = set()
    for a in existing:
        if a.name:
            names.add(a.name)
        if a.municipality_code:
            codes.add(a.municipality_code)
    return names, codes

def import_agencies_from_csv(csv_path: str, category_name: str, priority_default: int = 2):
    """CSVから発注機関をDBに投入する

    Args:
        csv_path: CSVファイルのパス
        category_name: カテゴリ名（国/都道府県/市区町村/外郭団体）
        priority_default: デフォルトの優先度（CSVに優先度が無い場合）
    """
    try:
        with get_db() as session:
            category = session.query(AgencyCategory).filter_by(name=category_name).first()
            if not category:
                logger.error(f"Category '{category_name}' not found. Run init_categories.py first.")
                return

            existing_names, existing_codes = _get_existing_keys(session)

            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                skipped = 0
                for row in reader:
                    name = row.get('agency_name') or row.get('name') or row.get('municipality_name')
                    municipality_code = row.get('municipality_code')
                    # 既存チェック（名称またはコードが既に存在する場合）
                    if name and name in existing_names:
                        skipped += 1
                        continue
                    if municipality_code and municipality_code in existing_codes:
                        skipped += 1
                        continue
                    try:
                        priority = int(row.get('priority_level', priority_default))
                    except (ValueError, TypeError):
                        priority = priority_default
                    agency = Agency(
                        name=name,
                        municipality_code=municipality_code,
                        category_id=category.id,
                        priority_level=priority
                    )
                    if 'base_url' in row:
                        agency.base_url = row['base_url']
                    session.add(agency)
                    if name:
                        existing_names.add(name)
                    if municipality_code:
                        existing_codes.add(municipality_code)
                    count += 1
                session.commit()
                logger.info(f"Imported {count} agencies from {csv_path} into '{category_name}', skipped {skipped} duplicates")
    except Exception as e:
        logger.error(f"Failed to import from {csv_path}: {e}")

if __name__ == "__main__":
    logger.info("Starting master agency import...")
    import_agencies_from_csv("data/master_ministries.csv", "国", priority_default=1)
    import_agencies_from_csv("data/master_prefectures.csv", "都道府県", priority_default=1)
    import_agencies_from_csv("data/master/municipality_codes.csv", "市区町村", priority_default=2)
    logger.info("Import completed.")
