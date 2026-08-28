from __future__ import annotations

from typing import List, Dict, Any

from sqlalchemy.orm import Session
from database.models.award_result import AwardResult
from database.models.bid import Bid
from database.models.extraction_result import ExtractionResult


class SimilarBidService:
    def __init__(self, session: Session):
        self.session = session

    def find_similar(self, bid_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        bid = self.session.get(Bid, bid_id)
        if not bid:
            return []
        category = bid.industry_category or ""
        results = (
            self.session.query(AwardResult)
            .filter(AwardResult.category == category)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "category": r.category,
                "budget_amount": r.budget_amount,
                "contract_amount": r.contract_amount,
                "award_rate": r.award_rate,
            }
            for r in results
        ]
