from datetime import date
from typing import Sequence

from sqlalchemy import and_, func, not_, or_

from database.engine import get_session
from database.models import Bid
from services.qualification_keyword_expander import expand_qualification_query


PAGE_SIZE = 20


def _contains(column, term: str):
    escaped = term.replace("/", "//").replace("%", "/%").replace("_", "/_")
    return func.coalesce(column, "").ilike(f"%{escaped}%", escape="/")


def _build_extracted_field_filters(
    budget_min: int | None = None,
    budget_max: int | None = None,
    qualification_keywords: str = "",
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    deliverables_keyword: str = "",
) -> list:
    """LLM抽出フィールドの検索条件リストを構築する。

    すべての条件はANDで結合される。空の入力は無視される。
    資格要件キーワードは辞書で同義語・関連語に展開され、
    展開語のいずれかに一致する案件を返す（語ごとにOR、語間はAND）。
    """
    conditions: list = []
    if budget_min is not None:
        conditions.append(Bid.budget_amount >= budget_min)
    if budget_max is not None:
        conditions.append(Bid.budget_amount <= budget_max)
    terms_by_token = [
        expand_qualification_query(token) for token in qualification_keywords.split()
    ]
    if any(terms_by_token):
        for terms in terms_by_token:
            conditions.append(or_(*(_contains(Bid.qualifications, term) for term in terms)))
    if deadline_from is not None:
        conditions.append(Bid.delivery_deadline >= deadline_from)
    if deadline_to is not None:
        conditions.append(Bid.delivery_deadline <= deadline_to)
    if deliverables_keyword.strip():
        for term in deliverables_keyword.split():
            conditions.append(_contains(Bid.deliverables, term))
    return conditions


def search_bids(
    keyword: str = "",
    prefecture: Sequence[str] | None = None,
    organization: str | None = None,
    bid_type: str | None = None,
    use_or: bool = False,
    use_not: bool = False,
    budget_min: int | None = None,
    budget_max: int | None = None,
    qualification_keywords: str = "",
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    deliverables_keyword: str = "",
    sort_column: str = "id",
    sort_direction: str = "asc",
    offset: int = 0,
    limit: int = PAGE_SIZE,
    allowed_prefectures: Sequence[str] | None = None,
) -> dict:
    if offset < 0 or limit < 1:
        raise ValueError("offset must be nonnegative and limit must be positive")
    with get_session() as session:
        if allowed_prefectures is not None and not allowed_prefectures:
            return {"results": [], "total": 0, "offset": offset, "limit": limit}
        query = session.query(
            Bid.id, Bid.filename, Bid.organization_name, Bid.announcement_date,
            Bid.budget_amount, Bid.qualifications, Bid.delivery_deadline, Bid.deliverables,
        )
        terms = keyword.split()
        if terms:
            matches = [
                or_(_contains(Bid.filename, term), _contains(Bid.notes, term))
                for term in terms
            ]
            if use_not:
                condition = not_(or_(*matches))
            else:
                condition = or_(*matches) if use_or else and_(*matches)
            query = query.filter(condition)
        if prefecture:
            query = query.filter(Bid.prefecture_code.in_(prefecture))
        if allowed_prefectures is not None:
            query = query.filter(Bid.prefecture_code.in_(allowed_prefectures))
        if organization and organization.strip():
            query = query.filter(_contains(Bid.organization_name, organization.strip()))
        if bid_type:
            query = query.filter(Bid.bid_type == bid_type)
        extracted_filters = _build_extracted_field_filters(
            budget_min=budget_min,
            budget_max=budget_max,
            qualification_keywords=qualification_keywords,
            deadline_from=deadline_from,
            deadline_to=deadline_to,
            deliverables_keyword=deliverables_keyword,
        )
        if extracted_filters:
            query = query.filter(and_(*extracted_filters))
        sort_columns = {
            "id": Bid.id,
            "announcement_date": Bid.announcement_date,
            "budget_amount": Bid.budget_amount,
            "delivery_deadline": Bid.delivery_deadline,
        }
        sort_key = sort_columns.get(sort_column, Bid.id)
        if sort_direction == "desc":
            direction = sort_key.desc().nullslast()
            tiebreak = Bid.id.desc()
        else:
            direction = sort_key.asc().nullslast()
            tiebreak = Bid.id.asc()
        total = query.count()
        rows = query.order_by(direction, tiebreak).offset(offset).limit(limit).all()
        return {
            "results": [
                {
                    "id": row.id,
                    "title": row.filename,
                    "organization": row.organization_name,
                    "announcement_date": row.announcement_date,
                    "budget_amount": row.budget_amount,
                    "qualification_requirements": row.qualifications,
                    "delivery_deadline": row.delivery_deadline,
                    "deliverables": row.deliverables,
                }
                for row in rows
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


def get_prefectures(allowed_prefectures: Sequence[str] | None = None) -> list[str]:
    with get_session() as session:
        if allowed_prefectures is not None and not allowed_prefectures:
            return []
        query = (
            session.query(Bid.prefecture_code)
            .filter(Bid.prefecture_code.isnot(None), Bid.prefecture_code != "")
        )
        if allowed_prefectures is not None:
            query = query.filter(Bid.prefecture_code.in_(allowed_prefectures))
        rows = query.distinct().order_by(Bid.prefecture_code).all()
        return [row[0] for row in rows]
