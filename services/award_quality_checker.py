"""
Award Quality Checker
落札結果DBのデータ品質を検証する。
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import AwardResult

logger = logging.getLogger(__name__)


def check_missing_award_rate(session: Session) -> List[Dict[str, Any]]:
    """award_rate が null のレコードを返す。"""
    stmt = select(AwardResult.id, AwardResult.project_name, AwardResult.source_url).where(
        AwardResult.award_rate.is_(None)
    )
    results = session.execute(stmt).all()
    return [
        {"id": r.id, "project_name": r.project_name, "source_url": r.source_url}
        for r in results
    ]


def check_missing_budget_amount(session: Session) -> List[Dict[str, Any]]:
    """budget_amount が null のレコードを返す。"""
    stmt = select(AwardResult.id, AwardResult.project_name, AwardResult.source_url).where(
        AwardResult.budget_amount.is_(None)
    )
    results = session.execute(stmt).all()
    return [
        {"id": r.id, "project_name": r.project_name, "source_url": r.source_url}
        for r in results
    ]


def check_missing_winner(session: Session) -> List[Dict[str, Any]]:
    """winner_name が null/空のレコードを返す。"""
    stmt = select(AwardResult.id, AwardResult.project_name, AwardResult.source_url).where(
        AwardResult.winner_name.is_(None)
    )
    results = session.execute(stmt).all()
    return [
        {"id": r.id, "project_name": r.project_name, "source_url": r.source_url}
        for r in results
    ]


def check_duplicate_entries(session: Session) -> List[Dict[str, Any]]:
    """source_url の重複を検出する。"""
    stmt = (
        select(AwardResult.source_url, func.count(AwardResult.id).label("count"))
        .where(AwardResult.source_url.is_not(None))
        .group_by(AwardResult.source_url)
        .having(func.count(AwardResult.id) > 1)
    )
    results = session.execute(stmt).all()
    return [{"source_url": r.source_url, "count": r.count} for r in results]


def get_quality_report(session: Session) -> Dict[str, Any]:
    """総合的なデータ品質レポートを返す。"""
    missing_rate = check_missing_award_rate(session)
    missing_budget = check_missing_budget_amount(session)
    missing_winner = check_missing_winner(session)
    duplicates = check_duplicate_entries(session)

    total_stmt = select(func.count(AwardResult.id))
    total = session.execute(total_stmt).scalar() or 0

    return {
        "total_awards": total,
        "missing_award_rate": len(missing_rate),
        "missing_budget": len(missing_budget),
        "missing_winner": len(missing_winner),
        "duplicate_source_urls": len(duplicates),
        "details": {
            "missing_award_rate": missing_rate[:10],
            "missing_budget": missing_budget[:10],
            "missing_winner": missing_winner[:10],
            "duplicates": duplicates,
        },
    }
