from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from database.models.procurement_forecast import CustomerForecastLink
from utils.forecast_logger import ForecastLogger


class ForecastCustomerLinkService:
    """営業担当者（顧客/ユーザー）と発注見通しを紐付ける。"""

    def __init__(self, session: Session):
        self.session = session
        self.logger = ForecastLogger("CustomerLink")

    def link(self, customer_id: int, forecast_id: int, interest_level: str = "medium", memo: Optional[str] = None) -> CustomerForecastLink:
        existing = (
            self.session.query(CustomerForecastLink)
            .filter(
                CustomerForecastLink.customer_id == customer_id,
                CustomerForecastLink.forecast_id == forecast_id,
            )
            .first()
        )
        if existing:
            existing.interest_level = interest_level
            existing.memo = memo
            self.session.commit()
            self.session.refresh(existing)
            return existing

        link = CustomerForecastLink(
            customer_id=customer_id,
            forecast_id=forecast_id,
            interest_level=interest_level,
            memo=memo,
            linked_at=datetime.utcnow(),
        )
        self.session.add(link)
        self.session.commit()
        self.session.refresh(link)
        return link

    def unlink(self, customer_id: int, forecast_id: int) -> bool:
        link = (
            self.session.query(CustomerForecastLink)
            .filter(
                CustomerForecastLink.customer_id == customer_id,
                CustomerForecastLink.forecast_id == forecast_id,
            )
            .first()
        )
        if link:
            self.session.delete(link)
            self.session.commit()
            return True
        return False

    def get_linked_forecasts(self, customer_id: int) -> List[CustomerForecastLink]:
        return (
            self.session.query(CustomerForecastLink)
            .filter(CustomerForecastLink.customer_id == customer_id)
            .all()
        )
