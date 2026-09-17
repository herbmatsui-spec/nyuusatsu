import contextvars
import datetime as dt
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func, select

from database.engine import get_session
from database.models._generated import AwardHistory, AwardResult, Bid, Competitor, Prefecture
from services.company_normalizer import normalize_company_name


_access_scope: contextvars.ContextVar = contextvars.ContextVar("award_access_scope", default=None)


def set_access_scope(scope: Optional[Dict[str, Any]]) -> contextvars.Token:
    """検索・集計に適用するアクセス範囲を設定する。

    scope の例: {"allowed_prefectures": ["13", "27"]}。None で解除する。
    """
    return _access_scope.set(scope)


def _scope_conditions() -> list:
    scope = _access_scope.get()
    if scope is None:
        return []
    allowed = scope.get("allowed_prefectures")
    if allowed is None:
        return []
    if not allowed:
        return [sqlalchemy_false()]
    return [select(Bid.id).where(
        Bid.id == AwardResult.tender_id,
        Bid.prefecture_code.in_(allowed),
    ).exists()]


def sqlalchemy_false():
    from sqlalchemy import false
    return false()


def _conditions(params: Dict[str, Any]) -> list:
    conditions = []
    if params.get("award_company"):
        normalized = normalize_company_name(params["award_company"])
        conditions.append(AwardResult.winner_normalized.contains(normalized, autoescape=True))
    if params.get("participant_company"):
        normalized = normalize_company_name(params["participant_company"])
        conditions.append(
            select(AwardHistory.id)
            .join(Competitor, Competitor.id == AwardHistory.competitor_id)
            .where(
                AwardHistory.award_result_id == AwardResult.id,
                Competitor.normalized_name.contains(normalized, autoescape=True),
            )
            .exists()
        )
    for key in ("project_name", "agency_name"):
        if params.get(key):
            conditions.append(getattr(AwardResult, key).contains(params[key], autoescape=True))
    if params.get("category"):
        categories = params["category"]
        conditions.append(AwardResult.category.in_(
            [categories] if isinstance(categories, str) else categories
        ))
    if params.get("prefectures"):
        conditions.append(select(Bid.id).where(
            Bid.id == AwardResult.tender_id,
            Bid.prefecture_code.in_(params["prefectures"]),
        ).exists())
    date_range = params.get("date_range")
    if date_range and len(date_range) == 2:
        start, end = date_range
        conditions.extend([
            AwardResult.award_date >= dt.datetime.combine(start, dt.time.min),
            AwardResult.award_date < dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min),
        ])
    return conditions


def search_award_results(params: Dict[str, Any], offset: int = 0, limit: int = 50) -> List[AwardResult]:
    conditions = _conditions(params)
    conditions.extend(_scope_conditions())
    with get_session() as session:
        query = select(AwardResult).where(*conditions).order_by(
            AwardResult.award_date.desc(), AwardResult.id.desc()
        ).offset(offset).limit(limit)
        return list(session.execute(query).scalars().all())


def search_award_results_count(params: Dict[str, Any]) -> int:
    conditions = _conditions(params)
    conditions.extend(_scope_conditions())
    with get_session() as session:
        return session.execute(
            select(func.count()).select_from(AwardResult).where(*conditions)
        ).scalar_one()


def get_company_win_rate(company_name: str) -> dict:
    with get_session() as session:
        normalized = normalize_company_name(company_name)
        conditions = [Competitor.normalized_name == normalized]
        conditions.extend(_scope_conditions())
        total, wins = session.execute(
            select(
                func.count(func.distinct(AwardHistory.award_result_id)),
                func.count(func.distinct(case(
                    (AwardHistory.is_winner.is_(True), AwardHistory.award_result_id),
                ))),
            ).join(Competitor, Competitor.id == AwardHistory.competitor_id)
            .join(AwardResult, AwardResult.id == AwardHistory.award_result_id)
            .where(*conditions)
        ).one()
        return {"wins": wins, "participations": total,
                "win_rate": wins / total * 100 if total else 0.0}


def get_distinct_categories() -> List[str]:
    with get_session() as session:
        return list(session.execute(
            select(AwardResult.category).distinct().where(
                AwardResult.category.is_not(None), AwardResult.category != ""
            ).order_by(AwardResult.category)
        ).scalars().all())


def get_prefecture_options() -> Dict[str, str]:
    with get_session() as session:
        return dict(session.execute(select(Prefecture.code, Prefecture.name).order_by(Prefecture.code)).all())


def get_participant_names(award_ids: List[int]) -> Dict[int, str]:
    if not award_ids:
        return {}
    with get_session() as session:
        rows = session.execute(
            select(AwardHistory.award_result_id, Competitor.normalized_name)
            .join(Competitor, Competitor.id == AwardHistory.competitor_id)
            .where(AwardHistory.award_result_id.in_(award_ids))
            .distinct().order_by(Competitor.normalized_name)
        ).all()
    names: Dict[int, List[str]] = {}
    for award_id, name in rows:
        names.setdefault(award_id, []).append(name)
    return {award_id: "、".join(values) for award_id, values in names.items()}


def get_monthly_award_counts(params: Dict[str, Any]) -> Dict[str, int]:
    """検索条件に一致する落札結果を月別に集計する（全ページ対象）"""
    with get_session() as session:
        rows = session.execute(
            select(AwardResult.award_date).where(*_conditions(params))
        ).scalars().all()
    counts: Dict[str, int] = {}
    for award_date in rows:
        if award_date:
            key = award_date.strftime("%Y-%m")
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
