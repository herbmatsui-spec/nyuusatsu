from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from sqlalchemy.orm import Session

from database.engine import SessionLocal
from search_api.forecast_schemas import ForecastResponse, ForecastListResponse
from services.forecast_search_service import ForecastSearchService
from utils.forecast_logger import ForecastLogger

router = APIRouter(prefix="/api/forecasts", tags=["forecasts"])


def get_search_service():
    db: Session = SessionLocal()
    try:
        yield ForecastSearchService(db)
    finally:
        db.close()


@router.get("", response_model=ForecastListResponse)
def list_forecasts(
    keyword: Optional[str] = Query(None),
    agency_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    fiscal_year: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service: ForecastSearchService = Depends(get_search_service),
):
    try:
        items, total = service.search(
            keyword=keyword,
            agency_id=agency_id,
            category=category,
            fiscal_year=fiscal_year,
            status=status,
            page=page,
            per_page=per_page,
        )
        return ForecastListResponse(
            items=[ForecastResponse.from_orm(i) for i in items],
            total=total,
            page=page,
            per_page=per_page,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{forecast_id}", response_model=ForecastResponse)
def get_forecast(
    forecast_id: int,
    service: ForecastSearchService = Depends(get_search_service),
):
    forecast = service.get_forecast_details(forecast_id)
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    return ForecastResponse.from_orm(forecast)
