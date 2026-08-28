from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher

from sqlalchemy.orm import Session
from database.models.procurement_forecast import ProcurementForecast
from utils.forecast_logger import ForecastLogger


class ForecastDedupService:
    """既存の発注見通し・入札案件との重複を検出する。"""

    def __init__(self, session: Session, similarity_threshold: float = 0.85):
        self.session = session
        self.threshold = similarity_threshold
        self.logger = ForecastLogger("DedupService")

    def find_duplicate(self, agency_id: int, title: str, fiscal_year: int) -> Optional[ProcurementForecast]:
        candidates = (
            self.session.query(ProcurementForecast)
            .filter(
                ProcurementForecast.agency_id == agency_id,
                ProcurementForecast.fiscal_year == fiscal_year,
            )
            .all()
        )
        for c in candidates:
            ratio = SequenceMatcher(None, c.title or "", title or "").ratio()
            if ratio >= self.threshold:
                return c
        return None

    def is_duplicate(self, agency_id: int, title: str, fiscal_year: int) -> bool:
        return self.find_duplicate(agency_id, title, fiscal_year) is not None

    def merge_data(self, existing: ProcurementForecast, new_data: Dict[str, Any]) -> ProcurementForecast:
        for key, value in new_data.items():
            if value is not None and hasattr(existing, key):
                setattr(existing, key, value)
        existing.updated_at = None  # モデルの onupdate で更新
        return existing
