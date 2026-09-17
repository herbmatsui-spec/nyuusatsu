"""
Specification Similarity Search Service

Search for bids and find similar specification texts using TF-IDF cosine
similarity. Provides both keyword-based bid search and specification
similarity search.
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.models import Bid
from services.text_similarity_service import TextSimilarityService

logger = logging.getLogger(__name__)


class SpecificationSimilarityService:
    """Specification text similarity search for bid documents."""

    def __init__(self, session: Session):
        self.session = session
        self._similarity_svc: Optional[TextSimilarityService] = None

    def _similarity_service(self) -> TextSimilarityService:
        if self._similarity_svc is None:
            self._similarity_svc = TextSimilarityService(self.session)
        return self._similarity_svc

    def search_bids(
        self,
        keyword: str = "",
        organization: str = "",
        prefecture_code: str = "",
        industry_category: str = "",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search bids by keyword, organization, prefecture, or industry.

        Searches across specification_text, deliverables, qualifications,
        organization_name and filename fields.
        """
        query = self.session.query(Bid)

        if keyword:
            pattern = f"%{keyword}%"
            query = query.filter(
                or_(
                    Bid.specification_text.ilike(pattern),
                    Bid.deliverables.ilike(pattern),
                    Bid.qualifications.ilike(pattern),
                    Bid.filename.ilike(pattern),
                )
            )

        if organization:
            org_pattern = f"%{organization}%"
            query = query.filter(Bid.organization_name.ilike(org_pattern))

        if prefecture_code:
            query = query.filter(Bid.prefecture_code == prefecture_code)

        if industry_category:
            query = query.filter(Bid.industry_category == industry_category)

        query = query.order_by(Bid.announcement_date.desc()).limit(limit)
        results = query.all()

        return [self._bid_to_dict(b) for b in results]

    def find_similar_bids(
        self,
        bid_id: int,
        n: Optional[int] = None,
        threshold: Optional[float] = None,
        months: Optional[int] = None,
        use_cache: bool = True,
        prefecture_code: str = "",
        industry_category: str = "",
    ) -> List[Dict[str, Any]]:
        """Find bids with similar specification text to the given bid.

        Args:
            bid_id: Base bid ID for comparison.
            n: Max results.
            threshold: Min similarity score.
            months: Time window in months.
            use_cache: Use LRU cache for repeated queries.

        Returns:
            List of similar bid dicts sorted by similarity score descending.
        """
        svc = self._similarity_service()

        search = svc.get_cached_top_n if use_cache else svc.get_top_n_similar
        return search(
            bid_id, n=n, threshold=threshold, months=months,
            prefecture_code=prefecture_code, industry_category=industry_category,
        )

    def get_all_prefectures(self) -> List[str]:
        """Get list of distinct prefecture codes from bids."""
        results = (
            self.session.query(Bid.prefecture_code)
            .filter(Bid.prefecture_code.isnot(None), Bid.prefecture_code != "")
            .distinct()
            .order_by(Bid.prefecture_code)
            .all()
        )
        return [r[0] for r in results]

    def get_all_industries(self) -> List[str]:
        """Get list of distinct industry categories from bids."""
        results = (
            self.session.query(Bid.industry_category)
            .filter(Bid.industry_category.isnot(None), Bid.industry_category != "")
            .distinct()
            .order_by(Bid.industry_category)
            .all()
        )
        return [r[0] for r in results]

    def _bid_to_dict(self, bid: Bid) -> Dict[str, Any]:
        """Convert a Bid model to a dict for display."""
        return {
            "id": bid.id,
            "title": bid.deliverables or bid.filename or "不明",
            "filename": bid.filename or "",
            "organization_name": bid.organization_name or "",
            "prefecture_code": bid.prefecture_code or "",
            "industry_category": bid.industry_category or "",
            "budget_amount": bid.budget_amount or 0,
            "budget": bid.budget or "",
            "announcement_date": bid.announcement_date.isoformat() if bid.announcement_date else "",
            "deadline": bid.deadline or "",
            "qualifications": bid.qualifications or "",
            "awarded_company": bid.awarded_company or "",
            "award_rate": bid.award_rate or 0,
            "specification_text": bid.specification_text or "",
        }

    def get_bid_detail(self, bid_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed info for a single bid."""
        bid = self.session.get(Bid, bid_id)
        if bid is None:
            return None
        return self._bid_to_dict(bid)
