from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from database.models.procurement_forecast import ProcurementForecast, ForecastStatus
from database.models.forecast_status import ForecastStatusEnum


class ForecastRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, forecast_data: dict) -> ProcurementForecast:
        forecast = ProcurementForecast(**forecast_data)
        self.session.add(forecast)
        self.session.commit()
        self.session.refresh(forecast)
        return forecast

    def get_by_id(self, forecast_id: int) -> Optional[ProcurementForecast]:
        return self.session.query(ProcurementForecast).filter(
            ProcurementForecast.id == forecast_id
        ).first()

    def get_by_agency(self, agency_id: int, limit: int = 100) -> List[ProcurementForecast]:
        return self.session.query(ProcurementForecast).filter(
            ProcurementForecast.agency_id == agency_id
        ).order_by(desc(ProcurementForecast.created_at)).limit(limit).all()

    def get_active(self, limit: int = 500) -> List[ProcurementForecast]:
        return self.session.query(ProcurementForecast).filter(
            or_(
                ProcurementForecast.status == "draft",
                ProcurementForecast.status == "published",
                ProcurementForecast.status == "updated",
            )
        ).order_by(desc(ProcurementForecast.created_at)).limit(limit).all()

    def get_by_fiscal_year(self, fiscal_year: int, agency_id: Optional[int] = None) -> List[ProcurementForecast]:
        query = self.session.query(ProcurementForecast).filter(
            ProcurementForecast.fiscal_year == fiscal_year
        )
        if agency_id:
            query = query.filter(ProcurementForecast.agency_id == agency_id)
        return query.order_by(desc(ProcurementForecast.created_at)).all()

    def get_by_category(self, category: str, limit: int = 100) -> List[ProcurementForecast]:
        return self.session.query(ProcurementForecast).filter(
            ProcurementForecast.category == category
        ).order_by(desc(ProcurementForecast.created_at)).limit(limit).all()

    def get_by_industry_category(self, industry_category: str, limit: int = 100) -> List[ProcurementForecast]:
        return self.session.query(ProcurementForecast).filter(
            ProcurementForecast.industry_category == industry_category
        ).order_by(desc(ProcurementForecast.created_at)).limit(limit).all()

    def search(self, keyword: str, limit: int = 100) -> List[ProcurementForecast]:
        search_pattern = f"%{keyword}%"
        return self.session.query(ProcurementForecast).filter(
            or_(
                ProcurementForecast.title.like(search_pattern),
                ProcurementForecast.description.like(search_pattern),
            )
        ).order_by(desc(ProcurementForecast.created_at)).limit(limit).all()

    def update_status(self, forecast_id: int, status: str, memo: Optional[str] = None) -> Optional[ProcurementForecast]:
        forecast = self.get_by_id(forecast_id)
        if forecast:
            forecast.status = status
            status_record = ForecastStatus(
                forecast_id=forecast_id,
                status=status,
                changed_at=datetime.utcnow(),
                memo=memo
            )
            self.session.add(status_record)
            self.session.commit()
            self.session.refresh(forecast)
        return forecast

    def update(self, forecast_id: int, update_data: dict) -> Optional[ProcurementForecast]:
        forecast = self.get_by_id(forecast_id)
        if forecast:
            for key, value in update_data.items():
                if hasattr(forecast, key):
                    setattr(forecast, key, value)
            forecast.updated_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(forecast)
        return forecast

    def link_to_bid(self, forecast_id: int, bid_id: int) -> Optional[ProcurementForecast]:
        return self.update(forecast_id, {"related_bid_id": bid_id, "status": ForecastStatusEnum.CLOSED.value})

    def delete(self, forecast_id: int) -> bool:
        forecast = self.get_by_id(forecast_id)
        if forecast:
            self.session.delete(forecast)
            self.session.commit()
            return True
        return False

    def count_by_status(self, status: str) -> int:
        return self.session.query(ProcurementForecast).filter(
            ProcurementForecast.status == status
        ).count()

    def get_paginated(self, page: int = 1, per_page: int = 20, status: Optional[str] = None) -> tuple:
        query = self.session.query(ProcurementForecast)
        if status:
            query = query.filter(ProcurementForecast.status == status)
        total = query.count()
        items = query.order_by(desc(ProcurementForecast.created_at)).offset((page - 1) * per_page).limit(per_page).all()
        return items, total