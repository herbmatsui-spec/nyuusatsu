import json
import logging
from database.base import Base
from database.models.url_registry import URLRegistry
from database.repositories.url_registry_repository import URLRegistryRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("registry_populator")

def populate_from_json(json_path: str):
    """
    JSON設定ファイルからURLレジストリにデータを移行する。
    """
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        repo = URLRegistryRepository(lambda: session)
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for agency_name, config in data.items():
            # 本来はJISコードなどの外部マスタから取得すべきだが、
            # 今回は移行のために一時的なコードを割り当てるか、
            # または既存のAgenciesテーブルからコードを検索する。
            # ここではデモとして、暫定的なコードを生成（実際にはマスタ連携が必要）
            # 本来の実装では AgencyRepository を使用して municipality_code を取得する
            
            # 暫定的に、名前からコードを検索するロジックを想定（実装は省略）
            # municipality_code = find_code_by_name(agency_name)
            
            # 今回はEhime.jsonの移行なので、仮のコードを付与して登録
            # 実際にはこのスクリプトを回す前に municipality_code マスタがあることが前提
            municipality_code = "UNKNOWN" 
            
            try:
                repo.add_registry(
                    municipality_code=municipality_code,
                    agency_name=agency_name,
                    base_url=config.get("entry_url", ""),
                    search_url=config.get("entry_url", ""), # search_urlがなければentry_urlで代用
                    parser_type="generic", # 初期はすべてGenericCrawlerで対応
                    max_depth=config.get("max_depth", 2)
                )
                logger.info(f"Registered {agency_name}")
            except Exception as e:
                logger.error(f"Failed to register {agency_name}: {e}")

if __name__ == "__main__":
    populate_from_json("crawler/parsers/agency_config/ehime.json")
