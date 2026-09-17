from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import date
from sqlalchemy.orm import Session

from database.engine import SessionLocal
from database.repositories import AwardResultRepository
from search_api.schemas import (
    AwardResultBase,
    AwardResultDetail,
    PaginatedResponse,
    PaginationParams,
)

router = APIRouter(prefix="/awards", tags=["awards"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/{award_id}", response_model=AwardResultDetail, responses={404: {"description": "Award result not found"}})
async def read_award(
    award_id: int,
    db: Session = Depends(get_db),
):
    """指定された ID の落札結果詳細を取得する。

    - **award_id**: 落札結果ID
    """
    repo = AwardResultRepository(db)
    award = repo.get_by_id(award_id)
    if not award:
        raise HTTPException(status_code=404, detail="Award result not found")
    return award


@router.get("", response_model=PaginatedResponse[AwardResultBase])
async def search_awards(
    q: Optional[str] = Query(None, description="キーワード検索（案件名・機関・落札者）"),
    winner_name: Optional[str] = Query(None, description="落札会社名"),
    agency_name: Optional[str] = Query(None, description="機関名"),
    budget_min: Optional[int] = Query(None, ge=0, description="予算額下限（円）"),
    budget_max: Optional[int] = Query(None, ge=0, description="予算額上限（円）"),
    awarded_after: Optional[date] = Query(None, description="落札日（開始）"),
    awarded_before: Optional[date] = Query(None, description="落札日（終了）"),
    bid_id: Optional[int] = Query(None, description="関連入札ID"),
    page: int = Query(PaginationParams.DEFAULT_PAGE, ge=1, description="ページ番号"),
    size: int = Query(PaginationParams.DEFAULT_SIZE, ge=1, le=PaginationParams.MAX_SIZE, description="ページサイズ"),
    db: Session = Depends(get_db),
):
    """落札結果を検索する。

    クエリパラメータでフィルタを指定でき、ページネーション付きの結果を返す。
    """
    repo = AwardResultRepository(db)
    results, total = repo.search(
        keyword=q,
        winner_name=winner_name,
        agency_name=agency_name,
        budget_min=budget_min,
        budget_max=budget_max,
        awarded_after=awarded_after,
        awarded_before=awarded_before,
        bid_id=bid_id,
        offset=(page - 1) * size,
        limit=size,
    )
    total_pages = (total + size - 1) // size if total > 0 else 0
    return PaginatedResponse(
        items=results,
        total=total,
        page=page,
        size=size,
        total_pages=total_pages,
    )
