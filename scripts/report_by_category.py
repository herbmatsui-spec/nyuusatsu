from database.models import AgencyCategory, Agency, Bid
from database.session import get_db
from sqlalchemy import func

def report_by_category():
    """
    カテゴリ別のAgency件数とBid件数を集計してレポート出力する
    """
    with get_db() as session:
        categories = session.query(AgencyCategory).order_by(AgencyCategory.priority).all()
        print(f"{'Category':<15} | {'Agency Count':<15} | {'Bid Count':<15}")
        print("-" * 45)
        
        for cat in categories:
            agency_count = session.query(Agency).filter(Agency.category_id == cat.id).count()
            
            # Agencyテーブル経由でBidをカウント
            bid_count = session.query(func.count(Bid.id)).\
                join(Agency, Bid.agency_id == Agency.id).\
                filter(Agency.category_id == cat.id).scalar()
            
            print(f"{cat.name:<15} | {agency_count:<15} | {bid_count:<15}")

if __name__ == "__main__":
    report_by_category()
