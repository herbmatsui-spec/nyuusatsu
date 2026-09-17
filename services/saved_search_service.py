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

    def create(self, user_id: str, name: str, criteria_json: str) -> SavedSearch:
        now = datetime.utcnow()
        user_id_int = int(user_id)
        return self.repo.create(
            user_id=user_id_int,
            name=name,
            criteria_json=criteria_json,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def get_active_by_user(self, user_id: str) -> List[SavedSearch]:
        user_id_int = int(user_id)
        return self.repo.get_active_by_user(user_id_int)

    def get_for_morning_digest(self) -> List[SavedSearch]:
        return self.repo.get_all_active()

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
        bid_dict = {
            "id": bid.id,
            "filename": bid.filename or "",
            "project_name": getattr(bid, "project_name", "") or "",
            "source_url": bid.source_url or "",
            "budget": bid.budget or "",
            "qualifications": bid.qualifications or "",
            "deadline": bid.deadline or "",
            "deliverables": bid.deliverables or "",
            "key_risks": bid.key_risks or "",
            "current_status": bid.current_status or "",
            "industry_category": bid.industry_category or "",
            "organization_name": bid.organization_name or "",
            "budget_amount": str(bid.budget_amount or ""),
        }
        for k, v in criteria.items():
            if not v:
                continue
            if k not in bid_dict:
                # Skip unknown filter keys (e.g., created_after, my_only, etc.)
                continue
            val = str(bid_dict.get(k, "")).lower()
            if str(v).lower() not in val:
                return False
        return True
