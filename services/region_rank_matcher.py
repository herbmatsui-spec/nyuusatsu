"""
Region Rank Matcher
地域別資格等级判定サービス。
"""
from typing import List, Optional
from database.engine import get_session
from database.repositories.company_profile_repository import CompanyRegionRankRepository
from database.models import Prefecture


REGION_BLOCKS: dict = {
    "北海道": ["01"],
    "東北": ["02", "03", "04", "05", "06", "07"],
    "関東": ["08", "09", "10", "11", "12", "13", "14"],
    "中部": ["15", "16", "17", "18", "19", "20", "21", "22", "23"],
    "近畿": ["24", "25", "26", "27", "28", "29", "30"],
    "中国": ["31", "32", "33", "34", "35"],
    "四国": ["36", "37", "38", "39"],
    "九州・沖縄": ["40", "41", "42", "43", "44", "45", "46", "47"],
}


def get_prefecture_codes_for_region(region_name: str) -> List[str]:
    return REGION_BLOCKS.get(region_name, [])


def get_region_block_for_prefecture_code(code: str) -> Optional[str]:
    for name, codes in REGION_BLOCKS.items():
        if code in codes:
            return name
    return None


def get_company_region_rank(
    company_profile_id: int,
    prefecture_code: str,
) -> Optional[str]:
    with get_session() as session:
        repo = CompanyRegionRankRepository(session)
        rank = repo.get_by_company_and_prefecture(company_profile_id, prefecture_code)
        return rank.region_rank if rank else None


def can_apply_in_region(
    company_profile_id: int,
    bid_prefecture_code: str,
) -> bool:
    rank = get_company_region_rank(company_profile_id, bid_prefecture_code)
    return bool(rank)


def find_available_regions(
    company_profile_id: int,
) -> List[str]:
    with get_session() as session:
        repo = CompanyRegionRankRepository(session)
        ranks = repo.list_by_company(company_profile_id)
        return [r.prefecture_code for r in ranks if r.region_rank]


def match_by_region_and_industry(
    company_profile_id: int,
    bid_prefecture_code: str,
    bid_category: Optional[str],
) -> bool:
    rank = get_company_region_rank(company_profile_id, bid_prefecture_code)
    if not rank:
        return False
    if bid_category and rank.category:
        return rank.category == bid_category or rank.category == "ALL"
    return True