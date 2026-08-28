"""
Seed Company Profile and Region Ranks
自社資格情報の初期登録スクリプト。
"""
import sys
sys.path.insert(0, ".")

import logging
from database.engine import get_session
from database.repositories.company_profile_repository import CompanyProfileRepository, CompanyRegionRankRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_company_profile() -> dict:
    with get_session() as session:
        profile_repo = CompanyProfileRepository(session)
        existing = profile_repo.session.query(profile_repo.model).first() if False else None
        from database.models import CompanyProfile
        existing = session.query(CompanyProfile).first()

        if not existing:
            profile = profile_repo.create({
                "name": "デモ企業",
                "unified_qualification_grade": "B",
            })
            logger.info(f"Created company profile: {profile.id}")
        else:
            profile = existing
            logger.info("Company profile already exists.")

        # Add region ranks for key prefectures
        region_repo = CompanyRegionRankRepository(session)
        regions = [
            {"prefecture_code": "13", "region_rank": "A", "category": "建設"},
            {"prefecture_code": "14", "region_rank": "B", "category": "建設"},
            {"prefecture_code": "27", "region_rank": "A", "category": "IT"},
        ]
        from database.models import CompanyRegionRank
        for r in regions:
            exists = session.query(CompanyRegionRank).filter(
                CompanyRegionRank.company_profile_id == profile.id,
                CompanyRegionRank.prefecture_code == r["prefecture_code"],
            ).first()
            if not exists:
                region_repo.create({
                    **r,
                    "company_profile_id": profile.id,
                })
                logger.info(f"Added region rank: {r['prefecture_code']}")

    return {"created_profile": bool(existing), "region_ranks_added": len(regions)}


if __name__ == "__main__":
    result = seed_company_profile()
    print(f"Result: {result}")