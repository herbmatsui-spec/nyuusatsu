from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from database.models.procurement_forecast import ProcurementForecast, ForecastStatus
from database.models.forecast_status import ForecastStatusEnum
from utils.forecast_logger import ForecastLogger


class ForecastBatchService:
    """発注見通しデータの一括登録・更新サービス。"""

    def __init__(self, session: Session):
        self.session = session
        self.logger = ForecastLogger("BatchService")

    def save_forecasts(self, agency_id: int, forecast_list: List[Dict[str, Any]]) -> List[ProcurementForecast]:
        saved: List[ProcurementForecast] = []
        try:
            for data in forecast_list:
                existing = (
                    self.session.query(ProcurementForecast)
                    .filter(
                        ProcurementForecast.agency_id == agency_id,
                        ProcurementForecast.title == data.get("title"),
                        ProcurementForecast.fiscal_year == data.get("fiscal_year"),
                    )
                    .first()
                )
                if existing:
                    for key, value in data.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                    saved.append(existing)
                else:
                    new_forecast = ProcurementForecast(agency_id=agency_id, **data)
                    self.session.add(new_forecast)
                    saved.append(new_forecast)
            self.session.commit()
            self.logger.info(f"Batch save completed", count=len(saved))
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Batch save failed", error=str(e))
            raise
        return saved

    def bulk_update_status(self, forecast_ids: List[int], status: str, memo: str = None):
        try:
            for fid in forecast_ids:
                forecast = self.session.query(ProcurementForecast).get(fid)
                if forecast:
                    forecast.status = status
                    self.session.add(
                        ForecastStatus(forecast_id=fid, status=status, changed_at=datetime.utcnow(), memo=memo)
                    )
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Bulk update failed", error=str(e))
            raise
