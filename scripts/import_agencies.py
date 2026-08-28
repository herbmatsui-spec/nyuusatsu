import csv
import os
import sys

# プロジェクトルートディレクトリをパスに追加してインポート可能にする
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import get_db
from database.models.agency import Agency
from database.models.crawl_config import CrawlConfig

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "agencies.csv")

def import_agencies():
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV file not found at {CSV_PATH}")
        sys.exit(1)

    print(f"Reading agencies from {CSV_PATH}...")
    
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} records. Importing into database...")

    with get_db() as session:
        try:
            for i, row in enumerate(rows, 1):
                name = row.get("name")
                agency_type = row.get("type")
                region = row.get("region")
                base_url = row.get("base_url")
                target_url = row.get("target_url")
                parser_type = row.get("parser_type", "heuristic")
                frequency = row.get("frequency", "daily")
                municipality_code = row.get("municipality_code")
                if municipality_code:
                    municipality_code = municipality_code.strip()
                    if not municipality_code:
                        municipality_code = None
                else:
                    municipality_code = None
                    
                category = row.get("category")
                is_active_str = row.get("is_active", "True").strip()
                is_active = is_active_str == "True"

                if not name:
                    print(f"Row {i}: Missing name, skipping.")
                    continue

                # Agencyの重複チェックと登録
                agency = session.query(Agency).filter(Agency.name == name).first()
            if not agency:
                agency = Agency(
                    name=name,
                    type=agency_type,
                    region=region,
                    base_url=base_url,
                    municipality_code=municipality_code,
                    category=category
                )
                session.add(agency)
                session.flush()  # ID取得のためにフラッシュ
                print(f"Created Agency: {name} (ID: {agency.id})")
            else:
                # 既存レコードの情報もアップデート
                agency.type = agency_type
                agency.region = region
                agency.base_url = base_url
                agency.municipality_code = municipality_code
                agency.category = category
                print(f"Updated Agency: {name} (ID: {agency.id})")

            # CrawlConfigの登録（重複がなければ）
            if target_url:
                config = session.query(CrawlConfig).filter(
                    CrawlConfig.agency_id == agency.id,
                    CrawlConfig.target_url == target_url
                ).first()
                if not config:
                    config = CrawlConfig(
                        agency_id=agency.id,
                        target_url=target_url,
                        parser_type=parser_type,
                        frequency=frequency,
                        is_active=is_active
                    )
                    session.add(config)
                    print(f"  -> Added CrawlConfig for {name}: {target_url} (parser: {parser_type}, active: {is_active})")
                else:
                    config.parser_type = parser_type
                    config.frequency = frequency
                    config.is_active = is_active
                    print(f"  -> Updated CrawlConfig for {name} with target_url: {target_url} (active: {is_active})")
        except Exception as e:
            print(f"Error during import: {e}")
            raise
 
    print("Import completed successfully.")

if __name__ == "__main__":
    import_agencies()
