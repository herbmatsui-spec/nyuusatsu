"""
Win Rate Prediction Service (0-1)

Provides an uncalibrated rule-based score, not a measured win probability.
"""
import logging
import re
import unicodedata
from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy import Integer, func, or_
from sqlalchemy.orm import Session

from database.models import Bid, Competitor, CompanyProfile, AwardResult, AwardHistory
from services.bid_difficulty_scorer import BidDifficultyScorer, past_award_filters
from crawler.utils.company_name_normalizer import normalize

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS: Dict[str, float] = {
    "company_win_rate": 0.40,
    "difficulty_inverse": 0.30,
    "agency_award_trend": 0.20,
    "qualification_match": 0.10,
}

DEFAULT_PARAMS: Dict[str, Any] = {
    "default_company_win_rate": 0.15,
    "default_agency_award_rate": 0.30,
    "default_qualification_match": 0.50,
}


class WinPredictionService:
    """Rule-based win score (0.0-1.0), with evidence coverage metadata."""

    def __init__(
        self,
        session: Session,
        company_name: Optional[str] = None,
        competitor_id: Optional[int] = None,
    ):
        self.session = session
        self.company_name = company_name
        self.competitor_id = competitor_id
        self.difficulty_scorer = BidDifficultyScorer(session)
        cfg = self._load_config()
        self.weights: Dict[str, float] = {
            k: float(v) for k, v in cfg.get("weights", DEFAULT_WEIGHTS).items()
        }
        self.params: Dict[str, Any] = cfg.get("params", DEFAULT_PARAMS)

    def _load_config(self) -> Dict[str, Any]:
        try:
            from services.prediction_model_config import get_config
            return get_config().get("win_predictor", {})
        except Exception:
            return {}

    def predict(self, bid: Bid) -> Dict[str, Any]:
        difficulty_result = self.difficulty_scorer.score(bid)
        difficulty_score = difficulty_result["score"]
        company_rate, company_count, missing_context = self._company_evidence(bid)
        agency_rate, agency_count = self._agency_evidence(bid)
        qualification, qualification_status = self._qualification_evidence(bid)
        breakdown = {
            "company_win_rate": company_rate,
            "difficulty_inverse": 1.0 - (difficulty_score / 100.0 * 0.5),
            "agency_award_trend": agency_rate,
            "qualification_match": qualification,
        }
        weights = {k: max(0.0, self.weights.get(k, DEFAULT_WEIGHTS[k])) for k in breakdown}
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()} if total_weight else dict(DEFAULT_WEIGHTS)
        win_rate = sum(breakdown[k] * weights[k] for k in breakdown)
        evidence = {
            "company_win_rate": float(company_count > 0),
            "difficulty_inverse": difficulty_result["confidence"]["evidence_coverage"],
            "agency_award_trend": float(agency_count > 0),
            "qualification_match": float(qualification_status in {"matched", "mismatched", "expired", "not_required"}),
        }
        return {
            "win_rate": round(max(0.0, min(1.0, win_rate)), 4),
            "breakdown": {k: round(v, 4) for k, v in breakdown.items()},
            "difficulty_score": round(difficulty_score, 1),
            "weights": weights,
            "score_kind": "uncalibrated_rule_based_score",
            "confidence": {
                "kind": "evidence_coverage",
                "calibrated": False,
                "evidence_coverage": round(sum(weights[k] * evidence[k] for k in evidence), 4),
                "missing_factors": [k for k, v in evidence.items() if v < 1.0],
                "sample_counts": {
                    "company_win_rate": company_count,
                    "agency_award_trend": agency_count,
                    "competition_rate": difficulty_result["confidence"]["sample_counts"]["competition_rate"],
                },
                "missing_context": missing_context,
                "qualification_status": qualification_status,
                "difficulty": difficulty_result["confidence"],
            },
        }

    def _get_company_win_rate(self, bid: Optional[Bid] = None) -> float:
        if bid is not None:
            return self._company_evidence(bid)[0]
        competitor = self._resolve_competitor()
        default = float(self.params.get("default_company_win_rate", 0.15))
        if competitor is None:
            return default
        total = self.session.query(func.count(AwardHistory.id)).filter(
            AwardHistory.competitor_id == competitor.id,
        ).scalar() or 0
        if not total:
            return default
        wins = self.session.query(func.count(AwardHistory.id)).filter(
            AwardHistory.competitor_id == competitor.id,
            AwardHistory.is_winner.is_(True),
        ).scalar() or 0
        return wins / total

    def _company_evidence(self, bid: Bid) -> tuple[float, int, list[str]]:
        default = float(self.params.get("default_company_win_rate", 0.15))
        missing = [name for name, value in (
            ("industry", bid.industry_category),
            ("region", bid.prefecture_code),
            ("budget_band", bid.budget_amount is not None and bid.budget_amount > 0),
        ) if not value]
        competitor = self._resolve_competitor()
        if missing or competitor is None:
            return default, 0, missing
        budget = bid.budget_amount
        bounds = (0, 1_000_000, 10_000_000, 100_000_000)
        lower = max(bound for bound in bounds if bound <= budget)
        upper = next((bound for bound in bounds if bound > budget), None)
        historical_budget = func.coalesce(AwardResult.budget_amount, Bid.budget_amount)
        query = (
            self.session.query(func.max(AwardHistory.is_winner.cast(Integer)))
            .join(AwardResult, AwardHistory.award_result_id == AwardResult.id)
            .join(Bid, AwardResult.tender_id == Bid.id)
            .filter(
                AwardHistory.competitor_id == competitor.id,
                func.coalesce(AwardResult.category, Bid.industry_category) == bid.industry_category,
                Bid.prefecture_code == bid.prefecture_code,
                historical_budget > 0,
                historical_budget >= lower,
                *past_award_filters(bid),
            )
        )
        if upper is not None:
            query = query.filter(historical_budget < upper)
        outcomes = query.group_by(AwardResult.id).all()
        if not outcomes:
            return default, 0, missing
        return sum(row[0] for row in outcomes) / len(outcomes), len(outcomes), missing

    @staticmethod
    def _normalized_name(name: Optional[str]) -> str:
        return normalize(unicodedata.normalize("NFKC", name or "")).casefold()

    def _resolve_competitor(self) -> Optional[Competitor]:
        if self.competitor_id is not None:
            return self.session.get(Competitor, self.competitor_id)
        normalized = self._normalized_name(self.company_name)
        if not normalized:
            return None
        matches = [row for row in self.session.query(Competitor).all()
                   if self._normalized_name(row.normalized_name) == normalized]
        return matches[0] if len(matches) == 1 else None

    def _get_agency_award_trend(self, bid: Bid) -> float:
        return self._agency_evidence(bid)[0]

    def _agency_evidence(self, bid: Bid) -> tuple[float, int]:
        default = float(self.params.get("default_agency_award_rate", 0.30))
        competitor = self._resolve_competitor()
        name = self._normalized_name(competitor.normalized_name if competitor else self.company_name)
        if not name or not bid.organization_name:
            return default, 0
        winners = self.session.query(AwardHistory.award_result_id).filter(
            AwardHistory.is_winner.is_(True),
        )
        results = self.session.query(AwardResult).filter(
            AwardResult.agency_name == bid.organization_name,
            *past_award_filters(bid, last_year=True),
            or_(
                func.trim(func.coalesce(AwardResult.winner_normalized, "")) != "",
                func.trim(func.coalesce(AwardResult.winner_name, "")) != "",
                AwardResult.id.in_(winners),
            ),
        ).all()
        if not results:
            return default, 0
        company_wins = set()
        if competitor is not None:
            company_wins = {row[0] for row in self.session.query(AwardHistory.award_result_id).filter(
                AwardHistory.competitor_id == competitor.id,
                AwardHistory.is_winner.is_(True),
                AwardHistory.award_result_id.in_([row.id for row in results]),
            ).all()}
        won = sum(
            row.id in company_wins or name in {
                self._normalized_name(row.winner_normalized), self._normalized_name(row.winner_name),
            } for row in results
        )
        return won / len(results), len(results)

    def _get_qualification_match(self, bid: Bid) -> float:
        return self._qualification_evidence(bid)[0]

    def _qualification_evidence(self, bid: Bid) -> tuple[float, str]:
        default = min(0.5, max(0.0, float(self.params.get("default_qualification_match", 0.50))))
        text = unicodedata.normalize("NFKC", bid.qualifications or "").strip()
        if re.fullmatch(r"(?:資格(?:要件)?(?:は|:)?\s*)?(?:特に)?(?:なし|不要)[。.]?", text):
            return 1.0, "not_required"
        grade = r'[「\"『]?([A-Da-d])[」\"』]?\s*(?:等級|級)?'
        match = re.fullmatch(
            r"(?:全省庁統一資格\s*[:：]?\s*(?:等級\s*)?)" + grade
            + r"((?:\s*(?:、|,|・|/|又は|または|若しくは|もしくは|及び|および)\s*"
            + grade + r")*)\s*(?:のいずれか)?\s*(?:が必要(?:です)?|を有する(?:こと)?|であること)?[。.]?",
            text,
        )
        if not match:
            return default, "unknown_requirements"
        grades = {match.group(1).upper()}
        grades.update(g.upper() for g in re.findall(r"(?<![A-Za-z])([A-Da-d])(?![A-Za-z])", match.group(2)))
        profile = self._get_company_profile()
        if profile is None:
            return default, "missing_profile"
        company_grade = unicodedata.normalize("NFKC", profile.unified_qualification_grade or "").strip().upper()
        if company_grade not in {"A", "B", "C", "D"}:
            return default, "unknown_company_grade"
        expiry = profile.unified_qualification_expire
        if isinstance(expiry, datetime):
            expiry = expiry.date()
        if not isinstance(expiry, date):
            return default, "unknown_expiry"
        if expiry < date.today():
            return 0.0, "expired"
        if company_grade not in grades:
            return 0.0, "mismatched"
        return 1.0, "matched"

    def _get_company_profile(self) -> Optional[CompanyProfile]:
        competitor = self._resolve_competitor() if self.competitor_id is not None else None
        if self.competitor_id is not None and competitor is None:
            return None
        name = self._normalized_name(competitor.normalized_name if competitor else self.company_name)
        if not name:
            return None
        matches = [row for row in self.session.query(CompanyProfile).all()
                   if self._normalized_name(row.name) == name]
        return matches[0] if len(matches) == 1 else None

    def get_win_rate_breakdown_text(self, result: Dict[str, Any]) -> str:
        weights = result.get("weights", {})
        breakdown = result.get("breakdown", {})
        lines = ["勝率予測の計算内訳（未較正のルールベーススコア）:"]
        for factor, weight in sorted(weights.items()):
            score = breakdown.get(factor, 0.0)
            contribution = round(score * weight, 4)
            lines.append(f"  - {factor}（{weight*100:.0f}%）: {score:.2f} → {contribution}")
        lines.append(f"  - 合計勝率スコア（実際の確率ではありません）: {result['win_rate']:.2%}")
        return "\n".join(lines)
