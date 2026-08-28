from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from database.models.procurement_forecast import ProcurementForecast, ForecastStatus
from database.models.forecast_status import ForecastStatusEnum
from utils.forecast_logger import ForecastLogger


class ForecastBidLinkService:
    """発注見通しが公示された際に Bid へ変換・紐付ける。"""

    def __init__(self, session: Session):
        self.session = session
        self.logger = ForecastLogger("BidLinkService")

    def link_to_bid(self, forecast_id: int, bid_id: int) -> Optional[ProcurementForecast]:
        forecast = self.session.query(ProcurementForecast).filter(ProcurementForecast.id == forecast_id).first()
        if not forecast:
            return None
        forecast.related_bid_id = bid_id
        forecast.status = ForecastStatusEnum.CLOSED.value
        now = datetime.utcnow()
        self.session.add(ForecastStatus(forecast_id=forecast_id, status=ForecastStatusEnum.CLOSED.value, changed_at=now, memo="公示済みBidと紐付け"))
        self.session.commit()
        self.session.refresh(forecast)
        return forecast

    def create_bid_from_forecast(self, forecast_id: int) -> Optional[int]:
        """発注見通しから新規 Bid レコードを生成し紐付ける（最低限のマッピング）。"""
        from database.models.bid import Bid

        forecast = self.session.query(ProcurementForecast).filter(ProcurementForecast.id == forecast_id).first()
        if not forecast:
            return None
        bid = Bid(
            prefecture_code=None,
            filename=forecast.title,
            source_url=forecast.source_url,
            budget=forecast.estimated_budget,
            budget_amount=forecast.estimated_budget_amount,
            industry_category=forecast.industry_category,
            organization_name=None,
            current_status="未確認",
        )
        self.session.add(bid)
        self.session.flush()
        forecast.related_bid_id = bid.id
        forecast.status = ForecastStatusEnum.CLOSED.value
        self.session.commit()
        return bid.id
