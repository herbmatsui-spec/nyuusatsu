from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from database.models.procurement_forecast import ProcurementForecast, ForecastStatus
from database.models.forecast_status import ForecastStatusEnum
from utils.forecast_logger import ForecastLogger


class ForecastUpdateService:
    """発注見通しのステータス更新・クローズ処理を行う。"""

    def __init__(self, session: Session):
        self.session = session
        self.logger = ForecastLogger("UpdateService")

    def update_status(self, forecast_id: int, status: str, memo: Optional[str] = None) -> Optional[ProcurementForecast]:
        forecast = self.session.query(ProcurementForecast).filter(ProcurementForecast.id == forecast_id).first()
        if not forecast:
            self.logger.warning(f"Forecast not found", forecast_id=forecast_id)
            return None
        forecast.status = status
        self.session.add(
            ForecastStatus(forecast_id=forecast_id, status=status, changed_at=datetime.utcnow(), memo=memo)
        )
        self.session.commit()
        self.session.refresh(forecast)
        return forecast

    def close_as_published(self, forecast_id: int, bid_id: Optional[int] = None) -> Optional[ProcurementForecast]:
        forecast = self.update_status(forecast_id, ForecastStatusEnum.CLOSED.value, "公示され入札案件へ移行")
        if forecast and bid_id:
            forecast.related_bid_id = bid_id
            self.session.commit()
        return forecast
