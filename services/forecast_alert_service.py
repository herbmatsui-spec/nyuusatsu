from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from database.models.procurement_forecast import ForecastAlertConfig, ProcurementForecast
from utils.forecast_logger import ForecastLogger


class ForecastAlertService:
    """業種・予算規模等で発注見通しアラート設定を管理する。"""

    def __init__(self, session: Session):
        self.session = session
        self.logger = ForecastLogger("AlertService")

    def create_config(
        self,
        customer_id: Optional[int] = None,
        user_id: Optional[int] = None,
        category: Optional[str] = None,
        min_budget_amount: Optional[int] = None,
        keyword: Optional[str] = None,
        agency_id: Optional[int] = None,
    ) -> ForecastAlertConfig:
        config = ForecastAlertConfig(
            customer_id=customer_id,
            user_id=user_id,
            category=category,
            min_budget_amount=min_budget_amount,
            keyword=keyword,
            agency_id=agency_id,
            is_active=1,
            created_at=datetime.utcnow(),
        )
        self.session.add(config)
        self.session.commit()
        self.session.refresh(config)
        return config

    def list_active(self) -> List[ForecastAlertConfig]:
        return self.session.query(ForecastAlertConfig).filter(ForecastAlertConfig.is_active == 1).all()

    def matches(self, config: ForecastAlertConfig, forecast: ProcurementForecast) -> bool:
        if config.category and forecast.category and config.category != forecast.category:
            return False
        if config.agency_id and forecast.agency_id != config.agency_id:
            return False
        if config.min_budget_amount and (forecast.estimated_budget_amount or 0) < config.min_budget_amount:
            return False
        if config.keyword and config.keyword not in (forecast.title or ""):
            return False
        return True

    def find_matching_forecasts(self, config: ForecastAlertConfig) -> List[ProcurementForecast]:
        forecasts = self.session.query(ProcurementForecast).all()
        return [f for f in forecasts if self.matches(config, f)]
