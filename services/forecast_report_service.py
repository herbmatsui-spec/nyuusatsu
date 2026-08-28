from typing import List, Dict, Any, Optional
from collections import defaultdict
from sqlalchemy.orm import Session

from database.models.procurement_forecast import ProcurementForecast
from database.models.forecast_status import ForecastStatusEnum
from utils.forecast_logger import ForecastLogger


class ForecastReportService:
    """営業向けの発注見通し分析レポートを生成する。"""

    def __init__(self, session: Session):
        self.session = session
        self.logger = ForecastLogger("ReportService")

    def summary_by_category(self, fiscal_year: Optional[int] = None) -> Dict[str, Any]:
        query = self.session.query(ProcurementForecast)
        if fiscal_year:
            query = query.filter(ProcurementForecast.fiscal_year == fiscal_year)

        forecasts = query.all()
        by_category = defaultdict(lambda: {"count": 0, "total_budget": 0})
        for f in forecasts:
            key = f.category or "未分類"
            by_category[key]["count"] += 1
            by_category[key]["total_budget"] += f.estimated_budget_amount or 0

        return dict(by_category)

    def summary_by_status(self) -> Dict[str, int]:
        forecasts = self.session.query(ProcurementForecast).all()
        counts = defaultdict(int)
        for f in forecasts:
            counts[f.status] += 1
        return dict(counts)

    def upcoming_forecasts(self, limit: int = 20) -> List[ProcurementForecast]:
        return (
            self.session.query(ProcurementForecast)
            .filter(ProcurementForecast.status.in_([ForecastStatusEnum.DRAFT.value, ForecastStatusEnum.PUBLISHED.value]))
            .order_by(ProcurementForecast.expected_publish_date.asc())
            .limit(limit)
            .all()
        )
