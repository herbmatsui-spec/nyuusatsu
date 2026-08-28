"""
Qualification Matcher
資格マッチングの核心エンジン。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

from database.engine import get_session
from database.repositories.company_profile_repository import CompanyProfileRepository, CompanyRegionRankRepository
from database.repositories.bid_repository import BidRepository
from services.grade_matcher import check_grade_requirement
from services.region_rank_matcher import can_apply_in_region, get_company_region_rank

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    bid_id: int
    can_apply: bool
    match_level: str  # "full", "partial", "none"
    missing_qualifications: List[str] = field(default_factory=list)
    missing_regions: List[str] = field(default_factory=list)
    score: float = 0.0  # 0.0-1.0
    messages: List[str] = field(default_factory=list)


class QualificationMatcher:
    def __init__(self, company_profile_id: int):
        self.company_profile_id = company_profile_id

    def _load_company_profile(self) -> Optional[Dict[str, Any]]:
        with get_session() as session:
            profile = session.get(CompanyProfileRepository(session).session.bind.get(CompanyProfileRepository(session).model), self.company_profile_id) if False else None
            repo = CompanyProfileRepository(session)
            profile = repo.get_by_id(self.company_profile_id)
            if not profile:
                return None

            region_ranks_repo = CompanyRegionRankRepository(session)
            region_ranks = region_ranks_repo.list_by_company(self.company_profile_id)

            return {
                "id": profile.id,
                "name": profile.name,
                "unified_qualification_grade": profile.unified_qualification_grade,
                "industry_category": profile.industry_category,
                "region_ranks": {r.prefecture_code: r.region_rank for r in region_ranks},
            }

    def match_bid(self, bid_id: int) -> MatchResult:
        company = self._load_company_profile()
        if not company:
            return MatchResult(
                bid_id=bid_id,
                can_apply=False,
                match_level="none",
                messages=["企業プロファイルが見つかりません"],
            )

        with get_session() as session:
            from database.models import Bid, BidQualificationTag, QualificationTag
            bid = session.get(Bid, bid_id)
            if not bid:
                return MatchResult(
                    bid_id=bid_id,
                    can_apply=False,
                    match_level="none",
                    messages=["案件が見つかりません"],
                )

            # Get required qualifications for this bid
            req_tags = (
                session.query(BidQualificationTag, QualificationTag)
                .join(QualificationTag, BidQualificationTag.tag_id == QualificationTag.id)
                .filter(BidQualificationTag.bid_id == bid_id)
                .all()
            )

            missing_qualifications = []
            missing_regions = []
            total_score = 0.0
            total_checks = 0

            for bt, qt in req_tags:
                total_checks += 1
                # Check grade requirement
                required_grade = bt.required_grade or qt.grade_required
                grade_ok = check_grade_requirement(
                    company["unified_qualification_grade"],
                    required_grade,
                )
                if not grade_ok:
                    missing_qualifications.append(f"等級不足: {required_grade or '不明'}")
                # Check region requirement
                required_region = bt.required_region or qt.region_required
                if required_region:
                    region_ok = can_apply_in_region(self.company_profile_id, required_region)
                    if not region_ok:
                        missing_regions.append(f"地域不足: {required_region}")

                # Score calculation
                if grade_ok and (not required_region or can_apply_in_region(self.company_profile_id, required_region)):
                    total_score += 1.0
                elif grade_ok or (required_region and can_apply_in_region(self.company_profile_id, required_region)):
                    total_score += 0.5

            final_score = total_score / total_checks if total_checks > 0 else 1.0

            if len(missing_qualifications) == 0 and len(missing_regions) == 0:
                match_level = "full"
                can_apply = True
            elif final_score >= 0.5:
                match_level = "partial"
                can_apply = True
            else:
                match_level = "none"
                can_apply = False

            messages = []
            if missing_qualifications:
                messages.extend(missing_qualifications)
            if missing_regions:
                messages.extend(missing_regions)

            return MatchResult(
                bid_id=bid_id,
                can_apply=can_apply,
                match_level=match_level,
                missing_qualifications=missing_qualifications,
                missing_regions=missing_regions,
                score=final_score,
                messages=messages,
            )

    def match_bids(self, filters: Optional[Dict[str, Any]] = None) -> List[MatchResult]:
        company = self._load_company_profile()
        if not company:
            return []

        with get_session() as session:
            repo = BidRepository(session)
            all_bids = repo.list_all(limit=1000)

        results = []
        for bid in all_bids:
            result = self.match_bid(bid.id)
            if filters:
                if filters.get("my_qualifications_only") and not result.can_apply:
                    continue
            results.append(result)

        return results