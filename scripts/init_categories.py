from database.models import AgencyCategory
from database.session import get_db

def init_agency_categories():
    """
    発注機関の基本カテゴリを初期投入する
    """
    categories = [
        {"name": "国", "description": "省庁・政府機関", "priority": 1},
        {"name": "都道府県", "description": "47都道府県", "priority": 2},
        {"name": "市区町村", "description": "市区町村", "priority": 3},
        {"name": "外郭団体", "description": "公社・公団・公立病院等", "priority": 4},
    ]
    
    with get_db() as session:
        for cat_data in categories:
            # 重複チェック
            exists = session.query(AgencyCategory).filter_by(name=cat_data["name"]).first()
            if not exists:
                category = AgencyCategory(**cat_data)
                session.add(category)
        session.commit()
        print("Successfully initialized agency categories.")

if __name__ == "__main__":
    init_agency_categories()
