"""
Prediction Dashboard Service

Provides a unified interface for the dashboard to compute and display
bid difficulty scores and win rate predictions. Combines data from
BidDifficultyScorer, WinPredictionService, and TextSimilarityService.
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import Bid
from services.bid_difficulty_scorer import BidDifficultyScorer
from services.win_prediction_service import WinPredictionService
from services.specification_similarity_service import SpecificationSimilarityService

logger = logging.getLogger(__name__)


class PredictionDashboardService:
    """Service layer for the prediction dashboard widgets."""

    def __init__(self, session: Session, company_name: Optional[str] = None):
        self.session = session
        self.company_name = company_name or self._get_default_company_name()
        self.difficulty_scorer = BidDifficultyScorer(session)
        self.win_predictor = WinPredictionService(
            session,
            company_name=self.company_name,
        )
        self.similarity_svc = SpecificationSimilarityService(session)

    def _get_default_company_name(self) -> Optional[str]:
        """Get the default company name from settings or environment."""
        try:
            from database.models import SystemSetting
            setting = self.session.get(SystemSetting, "default_company_name")
            if setting and setting.value:
                return setting.value
        except Exception:
            pass
        import os
        return os.getenv("DEFAULT_COMPANY_NAME") or None

    def get_bid_prediction(self, bid_id: int) -> Optional[Dict[str, Any]]:
        """Get difficulty and win prediction for a single bid.

        Compute company-specific predictions and matching breakdowns in real time.
        """
        bid = self.session.get(Bid, bid_id)
        if bid is None:
            return None

        difficulty_result = self.difficulty_scorer.score(bid)
        win_result = self.win_predictor.predict(bid)

        return {
            "bid": self._bid_summary(bid),
            "difficulty": {
                "score": difficulty_result["score"],
                "breakdown": difficulty_result["breakdown"],
                "weights": difficulty_result["weights"],
                "confidence": difficulty_result.get("confidence"),
                "explanation": self.difficulty_scorer.get_score_breakdown_text(difficulty_result),
            },
            "win_prediction": {
                "win_rate": win_result["win_rate"],
                "breakdown": win_result["breakdown"],
                "weights": win_result["weights"],
                "difficulty_score": win_result["difficulty_score"],
                "confidence": win_result.get("confidence"),
                "explanation": self.win_predictor.get_win_rate_breakdown_text(win_result),
            },
            "from_cache": False,
        }

    def get_difficulty_gauge_data(self, difficulty_score: float) -> Dict[str, Any]:
        """Generate gauge visualization data for a difficulty score (0-100)."""
        if difficulty_score < 30:
            color = "green"
            label = "低"
        elif difficulty_score < 60:
            color = "yellow"
            label = "中"
        else:
            color = "red"
            label = "高"

        return {
            "score": difficulty_score,
            "color": color,
            "label": label,
            "max_score": 100.0,
        }

    def get_win_rate_gauge_data(self, win_rate: float) -> Dict[str, Any]:
        """Generate gauge visualization data for a win rate (0-1)."""
        if win_rate >= 0.30:
            color = "green"
        elif win_rate >= 0.15:
            color = "yellow"
        else:
            color = "red"

        return {
            "win_rate": win_rate,
            "color": color,
            "percentage": round(win_rate * 100, 1),
        }

    def search_bids_for_prediction(
        self,
        keyword: str = "",
        organization: str = "",
        prefecture_code: str = "",
        industry_category: str = "",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search bids for the prediction dashboard."""
        return self.similarity_svc.search_bids(
            keyword=keyword,
            organization=organization,
            prefecture_code=prefecture_code,
            industry_category=industry_category,
            limit=limit,
        )

    def get_recent_bids(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recently announced bids for quick selection."""
        bids = (
            self.session.query(Bid)
            .filter(Bid.announcement_date.isnot(None))
            .order_by(Bid.announcement_date.desc())
            .limit(limit)
            .all()
        )
        return [self._bid_summary(b) for b in bids]

    def _bid_summary(self, bid: Bid) -> Dict[str, Any]:
        return {
            "id": bid.id,
            "title": bid.deliverables or bid.filename or "",
            "organization_name": bid.organization_name or "",
            "prefecture_code": bid.prefecture_code or "",
            "industry_category": bid.industry_category or "",
            "budget_amount": bid.budget_amount or 0,
            "announcement_date": bid.announcement_date.isoformat() if bid.announcement_date else "",
            "deadline": bid.deadline or "",
            "bid_difficulty_score": bid.bid_difficulty_score,
            "win_prediction_score": bid.win_prediction_score,
        }
