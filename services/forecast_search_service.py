from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from database.models.procurement_forecast import ProcurementForecast
from utils.forecast_logger import ForecastLogger


class ForecastSearchService:
    """発注見通しデータの検索サービス。"""

    def __init__(self, session: Session):
        self.session = session
        self.logger = ForecastLogger("SearchService")

    def search(
        self,
        keyword: Optional[str] = None,
        agency_id: Optional[int] = None,
        category: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[ProcurementForecast], int]:
        query = self.session.query(ProcurementForecast)
        if keyword:
            p = f"%{keyword}%"
            query = query.filter(
                or_(
                    ProcurementForecast.title.like(p),
                    ProcurementForecast.description.like(p),
                    ProcurementForecast.category.like(p),
                )
            )
        if agency_id:
            query = query.filter(ProcurementForecast.agency_id == agency_id)
        if category:
            query = query.filter(ProcurementForecast.category == category)
        if fiscal_year:
            query = query.filter(ProcurementForecast.fiscal_year == fiscal_year)
        if status:
            query = query.filter(ProcurementForecast.status == status)

        total = query.count()
        items = (
            query.order_by(desc(ProcurementForecast.created_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    def get_forecast_details(self, forecast_id: int) -> Optional[ProcurementForecast]:
        return self.session.query(ProcurementForecast).filter(ProcurementForecast.id == forecast_id).first()
