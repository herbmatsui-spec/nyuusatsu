from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.repositories.saved_search_repository import SavedSearchRepository
from database.repositories.bid_repository import BidRepository


class SavedSearchService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = SavedSearchRepository(session)
        self.bid_repo = BidRepository(session)

    def create(self, user_id: str, name: str, criteria: Dict[str, Any]) -> SavedSearch:
        now = datetime.utcnow()
        return self.repo.create(
            user_id=user_id,
            name=name,
            criteria_json=json.dumps(criteria, ensure_ascii=False),
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def get_active_by_user(self, user_id: str) -> List[SavedSearch]:
        return self.repo.get_active_by_user(user_id)

    def get_for_morning_digest(self) -> List[SavedSearch]:
        return self.repo.get_for_morning_digest()

    def match_new_bids(self, saved_search: SavedSearch, since: datetime) -> List[Dict[str, Any]]:
        criteria = json.loads(saved_search.criteria_json or "{}")
        bids = self.bid_repo.list_all(limit=1000)
        matched = []
        for bid in bids:
            if bid.created_at and bid.created_at < since:
                continue
            if self._matches(bid, criteria):
                matched.append({
                    "id": bid.id,
                    "filename": bid.filename,
                    "organization_name": bid.organization_name,
                    "budget": bid.budget,
                })
        return matched

    def mark_notified(self, saved_search: SavedSearch) -> None:
        saved_search.last_notified_at = datetime.utcnow()
        self.session.flush()

    def _matches(self, bid, criteria: Dict[str, Any]) -> bool:
        if not criteria:
            return True
        if "keywords" in criteria:
            keyword = str(criteria["keywords"]).lower()
            hay = f"{bid.filename or ''} {bid.budget or ''} {bid.qualifications or ''} {bid.deliverables or ''}".lower()
            if keyword not in hay:
                return False
        if "min_budget" in criteria:
            try:
                if (bid.budget_amount or 0) < int(criteria["min_budget"]):
                    return False
            except (TypeError, ValueError):
                pass
        if "prefecture" in criteria:
            org = str(bid.organization_name or "")
            if criteria["prefecture"] not in org:
                return False
        if "category" in criteria:
            if str(criteria["category"]) != str(bid.industry_category or ""):
                return False
        return True
