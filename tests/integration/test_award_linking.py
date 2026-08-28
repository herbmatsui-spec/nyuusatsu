import pytest
from services.award_result_service import AwardResultService
from database.models import Bid
from database.engine import get_session

def test_link_award_to_bid():
    # テスト用Bidを作成
    with get_session() as session:
        bid = Bid(filename="test_bid.pdf", organization_name="テスト機関", budget_amount=1000000)
        session.add(bid)
        session.commit()
        bid_id = bid.id
    
    # 落札データ
    award_data = {
        "title": "test_bid.pdf", # filenameをtitleとして検索する想定
        "company": "テスト業者",
        "amount": "900,000円",
        "opened_at": "2026-07-06"
    }
    
    service = AwardResultService()
    service.link_award_to_bid(award_data)
    
    # 確認
    with get_session() as session:
        bid = session.get(Bid, bid_id)
        assert bid.awarded_company == "テスト業者"
        assert bid.actual_bid_amount == 900000
        assert bid.award_rate == 90.0
        assert bid.current_status == "落札"
