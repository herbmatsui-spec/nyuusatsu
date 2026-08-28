"""
Award Calculator
落札率算出・金額パース・業種別統計を提供する。
"""
from typing import Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import AwardResult


def calculate_award_rate(budget: Optional[float], contract: Optional[float]) -> Optional[float]:
    if budget and contract and budget > 0:
        return round((contract / budget) * 100, 2)
    return None


def parse_amount_text(text: str) -> Optional[int]:
    """金額テキストを整数に変換する。"""
    if not text:
        return None
    import re
    cleaned = text.replace(",", "").replace("円", "").replace(" ", "").replace("\n", "")
    m = re.search(r"(\d+)", cleaned)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def enrich_award_rate(award_dict: Dict) -> Dict:
    """award_result の辞書に award_rate を追加して返す。"""
    budget = award_dict.get("budget_amount")
    contract = award_dict.get("contract_amount")
    if budget is not None and contract is not None:
        award_dict["award_rate"] = calculate_award_rate(float(budget), float(contract))
    return award_dict


def get_industry_avg_award_rate(session: Session, industry: str) -> Dict[str, Optional[float]]:
    """指定業種の平均落札率・中央値を算出。"""
    stmt = select(
        func.avg(AwardResult.award_rate).label("avg_rate"),
        func.min(AwardResult.award_rate).label("min_rate"),
        func.max(AwardResult.award_rate).label("max_rate"),
    ).where(AwardResult.category == industry)
    result = session.execute(stmt).one_or_none()
    if result and result.avg_rate is not None:
        return {
            "industry": industry,
            "avg_rate": round(float(result.avg_rate), 2),
            "min_rate": round(float(result.min_rate), 2),
            "max_rate": round(float(result.max_rate), 2),
        }
    return {"industry": industry, "avg_rate": None, "min_rate": None, "max_rate": None}


def get_overall_award_rate_stats(session: Session) -> Dict[str, Optional[float]]:
    """全件の平均落札率を算出。"""
    stmt = select(
        func.avg(AwardResult.award_rate).label("avg_rate"),
        func.count(AwardResult.id).label("total"),
    )
    result = session.execute(stmt).one_or_none()
    return {
        "total_awards": result.total if result else 0,
        "avg_award_rate": round(float(result.avg_rate), 2) if result and result.avg_rate else None,
    }
