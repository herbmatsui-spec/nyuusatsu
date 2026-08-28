import sys
sys.path.append('D:/入札システム')
from database.session import get_db
from database.models.agency import Agency

def tag_agency_systems():
    with get_db() as session:
        # Get agencies without system_type
        agencies = session.query(Agency).filter(Agency.system_type.is_(None)).all()
        count = 0
        for agency in agencies:
            if not agency.category:
                continue
            cat_name = agency.category.name
            if cat_name == '国':
                agency.system_type = 'GEPS'
            elif cat_name == '都道府県':
                agency.system_type = '自治体共通'
            elif cat_name == '市区町村':
                agency.system_type = '自治体独自'
            elif cat_name == '外郭団体':
                agency.system_type = '外郭'
            else:
                agency.system_type = 'その他'
            count += 1
        session.commit()
        print(f"Tagged {count} agencies")

if __name__ == "__main__":
    tag_agency_systems()
