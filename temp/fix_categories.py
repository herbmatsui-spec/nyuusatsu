import sys
sys.path.append('D:/入札システム')
from database.session import get_db
from database.models.agency_category import AgencyCategory
with get_db() as session:
    # Delete all categories
    session.query(AgencyCategory).delete()
    # Re-insert categories using Unicode strings
    categories = [
        ("国", "省庁・政府機関", 1),
        ("都道府県", "47都道府県", 2),
        ("市区町村", "市区町村", 3),
        ("外郭団体", "公社・公団・公立病院等", 4),
    ]
    for cat_data in categories:
        category = AgencyCategory(name=cat_data[0], description=cat_data[1], priority=cat_data[2])
        session.add(category)
    session.commit()
    print("Re-inserted categories")
    for c in session.query(AgencyCategory).all():
        print(c.id, repr(c.name))
