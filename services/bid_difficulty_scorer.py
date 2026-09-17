"""
Bid Difficulty Scorer (0-100)

Computes a difficulty score for procurement bids based on multiple factors.
Each factor is normalized to 0-1 and combined via weighted average.

Factors:
  1. 予算額の対数尺度 (budget)     - higher budget -> higher difficulty
  2. 資格要件の項目数 (qualifications) - more items -> higher difficulty
  3. 納期のタイトさ (deadline)     - shorter deadline -> higher difficulty
  4. 過去の競争率 (competition_rate) - more bidders historically -> higher difficulty
  5. 仕様書の長さ (spec_length)    - longer spec -> higher difficulty
"""
import re
import math
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database.models import Bid, AwardResult, AwardHistory
from crawler.utils.date_parser import parse_date_string, extract_date_from_text
from services.similarity_preprocess import preprocess_specification


def history_cutoff(bid: Optional[Bid] = None) -> datetime:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    announced = getattr(bid, "announcement_date", None)
    if isinstance(announced, datetime):
        if announced.tzinfo is not None:
            announced = announced.astimezone(timezone.utc).replace(tzinfo=None)
        return min(now, announced)
    if isinstance(announced, date):
        return min(now, datetime.combine(announced, datetime.min.time()))
    return now


def past_award_filters(bid: Optional[Bid] = None, last_year: bool = False) -> list:
    cutoff = history_cutoff(bid)
    filters = [AwardResult.award_date < cutoff]
    if last_year:
        filters.append(AwardResult.award_date >= cutoff - timedelta(days=365))
    if bid is not None and bid.id is not None:
        filters.append(or_(AwardResult.tender_id.is_(None), AwardResult.tender_id != bid.id))
    return filters

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS: Dict[str, float] = {
    "budget": 0.30,
    "qualifications": 0.20,
    "deadline": 0.20,
    "competition_rate": 0.15,
    "spec_length": 0.15,
}

DEFAULT_PARAMS: Dict[str, Any] = {
    "budget_log_base": 10,
    "spec_length_log_base": 10,
    "default_competition_rate": 3.0,
    "default_days_to_deadline": 30,
}

# Normalization constants (log-scale caps)
_BUDGET_MAX_LOG = 8.0  # log10(100M yen) -> 1.0
_SPEC_LENGTH_MAX_LOG = 5.0  # log10(100K chars) -> 1.0
_QUALIFICATION_MAX_ITEMS = 15  # 15 items -> 1.0
_COMPETITION_MAX_BIDDERS = 15  # 15 bidders -> 1.0
_DEADLINE_MIN_DAYS = 3  # 3 days or less -> 1.0
_DEADLINE_MAX_DAYS = 60  # 60+ days -> 0.0


class BidDifficultyScorer:
    """Rule-based bid difficulty scorer (0-100)."""

    def __init__(self, session: Session):
        self.session = session
        cfg = self._load_config()
        self.weights: Dict[str, float] = {
            k: float(v) for k, v in cfg.get("weights", DEFAULT_WEIGHTS).items()
        }
        self.params: Dict[str, Any] = cfg.get("params", DEFAULT_PARAMS)

    def _load_config(self) -> Dict[str, Any]:
        try:
            from services.prediction_model_config import get_config
            return get_config().get("difficulty_scorer", {})
        except Exception:
            return {}

    def score(self, bid: Bid) -> Dict[str, Any]:
        """Compute difficulty score for a bid.

        Returns:
            {
                "score": float,          # 0.0-100.0
                "breakdown": {           # 0.0-1.0 per component
                    "budget": float,
                    "qualifications": float,
                    "deadline": float,
                    "competition_rate": float,
                    "spec_length": float,
                },
                "weights": {str: float}, # weight per component
            }
        """
        competition, sample_count = self._competition_evidence(bid)
        available = {
            "budget": bid.budget_amount is not None and bid.budget_amount > 0,
            "qualifications": bool((bid.qualifications or "").strip()),
            "deadline": self._extract_deadline_date(bid) is not None,
            "competition_rate": sample_count > 0,
            "spec_length": bool(self._get_spec_text(bid)),
        }
        components: Dict[str, float] = {
            "budget": self._score_budget(bid) if available["budget"] else 0.5,
            "qualifications": self._score_qualifications(bid) if available["qualifications"] else 0.5,
            "deadline": self._score_deadline(bid),
            "competition_rate": competition,
            "spec_length": self._score_spec_length(bid) if available["spec_length"] else 0.5,
        }
        weights = {k: max(0.0, self.weights.get(k, DEFAULT_WEIGHTS[k])) for k in components}
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()} if total_weight else dict(DEFAULT_WEIGHTS)
        score = round(sum(components[k] * weights[k] for k in components) * 100, 1)
        coverage = sum(weights[k] for k in components if available[k])
        return {
            "score": score,
            "breakdown": {k: round(v, 4) for k, v in components.items()},
            "weights": weights,
            "confidence": {
                "kind": "evidence_coverage",
                "calibrated": False,
                "evidence_coverage": round(coverage, 4),
                "missing_factors": [k for k in components if not available[k]],
                "sample_counts": {"competition_rate": sample_count},
            },
        }

    def _score_budget(self, bid: Bid) -> float:
        """予算額の対数尺度で正規化。"""
        budget = bid.budget_amount
        if not budget or budget <= 0:
            return 0.0
        log_budget = math.log10(budget + 1)
        return min(log_budget / _BUDGET_MAX_LOG, 1.0)

    def _score_qualifications(self, bid: Bid) -> float:
        """資格要件テキストから項目数をカウントし正規化。"""
        text = bid.qualifications or ""
        if not text.strip():
            return 0.0
        items = re.split(r"[・\n]", text)
        items = [i.strip() for i in items if i.strip()]
        return min(len(items) / _QUALIFICATION_MAX_ITEMS, 1.0)

    def _score_deadline(self, bid: Bid) -> float:
        """納期がタイトなほど高スコア。納期が過去または未設定ならデフォルト."""
        deadline_date = self._extract_deadline_date(bid)
        days_remaining = (
            (deadline_date - date.today()).days if deadline_date is not None
            else float(self.params.get("default_days_to_deadline", 30))
        )
        if days_remaining <= 0:
            return 1.0  # Past or today = maximum difficulty
        # Inverse normalization: shorter deadline = higher score
        score = (_DEADLINE_MAX_DAYS - days_remaining) / (_DEADLINE_MAX_DAYS - _DEADLINE_MIN_DAYS)
        return max(0.0, min(1.0, score))

    def _extract_deadline_date(self, bid: Bid) -> Optional[date]:
        """Extract deadline date from bid, trying multiple sources."""
        for value in (bid.delivery_deadline, bid.deadline):
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            if isinstance(value, str) and value.strip():
                parsed = parse_date_string(value) or extract_date_from_text(value)
                if parsed:
                    return parsed.date() if isinstance(parsed, datetime) else parsed
        return None

    def _score_competition_rate(self, bid: Bid) -> float:
        """過去の競争率（同機関の平均応札社数）で正規化。"""
        return self._competition_evidence(bid)[0]

    def _competition_evidence(self, bid: Bid) -> tuple[float, int]:
        if not bid.organization_name or not bid.industry_category:
            return self._default_competition_score(), 0
        counts = (
            self.session.query(func.count(func.distinct(AwardHistory.competitor_id)))
            .join(AwardResult, AwardHistory.award_result_id == AwardResult.id)
            .outerjoin(Bid, AwardResult.tender_id == Bid.id)
            .filter(
                AwardResult.agency_name == bid.organization_name,
                func.coalesce(AwardResult.category, Bid.industry_category) == bid.industry_category,
                *past_award_filters(bid, last_year=True),
            )
            .group_by(AwardResult.id)
            .all()
        )
        if not counts:
            return self._default_competition_score(), 0
        average = sum(row[0] for row in counts) / len(counts)
        return min(average / _COMPETITION_MAX_BIDDERS, 1.0), len(counts)

    def _default_competition_score(self) -> float:
        """Return default competition score from config params."""
        default_rate = float(self.params.get("default_competition_rate", 3.0))
        return min(default_rate / _COMPETITION_MAX_BIDDERS, 1.0)

    def _score_spec_length(self, bid: Bid) -> float:
        """仕様書テキストの長さの対数尺度で正規化。"""
        text = self._get_spec_text(bid)
        if not text:
            return 0.0
        log_len = math.log10(len(text) + 1)
        return min(log_len / _SPEC_LENGTH_MAX_LOG, 1.0)

    def _get_spec_text(self, bid: Bid) -> str:
        """Get specification text, preferring cleaned version."""
        if bid.specification_text_clean is not None:
            return preprocess_specification(bid.specification_text_clean)
        if bid.specification_text is not None:
            return preprocess_specification(bid.specification_text)
        return preprocess_specification(bid.deliverables or "")

    def score_bids_batch(self, bid_ids: list[int]) -> Dict[int, Dict[str, Any]]:
        """Score multiple bids at once."""
        results: Dict[int, Dict[str, Any]] = {}
        for bid_id in bid_ids:
            bid = self.session.get(Bid, bid_id)
            if bid:
                results[bid_id] = self.score(bid)
        return results

    def get_score_breakdown_text(self, result: Dict[str, Any]) -> str:
        """Generate a human-readable explanation of the difficulty score."""
        weights = result.get("weights", {})
        breakdown = result.get("breakdown", {})
        lines = ["難易度スコアの計算内訳:"]
        for factor, weight in sorted(weights.items()):
            score = breakdown.get(factor, 0.0)
            contribution = round(score * weight * 100, 1)
            lines.append(f"  - {factor}（{weight*100:.0f}%）: {score:.2f} → {contribution}点")
        lines.append(f"  - 合計: {result['score']} / 100")
        return "\n".join(lines)
