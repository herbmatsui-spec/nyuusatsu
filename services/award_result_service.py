from typing import Dict, Any, Optional
from database.repositories.bid_repository import BidRepository
from database.engine import get_session
import logging
from datetime import datetime
from utils.date_parser import parse_date

logger = logging.getLogger(__name__)

class AwardResultService:
    def __init__(self):
        self.bid_repo = None

    def _get_repo(self, session):
        if not self.bid_repo:
            self.bid_repo = BidRepository(session)
        return self.bid_repo

    def link_award_to_bid(self, award_data: Dict[str, Any]):
        """落札結果を既存のBidに紐付ける"""
        with get_session() as session:
            repo = self._get_repo(session)
            
            # 案件名（filename）で検索（簡易的なマッチング）
            # 実際には発注機関なども含めて検索する必要がある
            bid = repo.get_by_filename(award_data["title"])
            
            if not bid:
                logger.warning(f"Bid not found for: {award_data['title']}")
                return
            
            # 落札情報を更新
            parsed_date = parse_date(award_data.get("opened_at", ""))
            awarded_date = datetime.combine(parsed_date, datetime.min.time()) if parsed_date else None

            update_data = {
                "awarded_company": award_data["company"],
                "awarded_date": awarded_date,
                "current_status": "落札"
            }
            
            # 金額のパース（数値化）
            try:
                amount = int(award_data["amount"].replace(",", "").replace("円", ""))
                update_data["actual_bid_amount"] = amount
                if bid.budget_amount and bid.budget_amount > 0:
                    update_data["award_rate"] = (amount / bid.budget_amount) * 100
            except Exception as e:
                logger.error(f"Failed to parse amount: {e}")
            
            repo.update(bid, update_data)
            repo.add_status_history(bid.id, "落札", memo=f"{award_data['company']} が落札")
            logger.info(f"Linked award to bid: {bid.id}")
