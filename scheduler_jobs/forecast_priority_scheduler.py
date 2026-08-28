from typing import List, Dict, Any
from database.session import get_db
from database.models.agency import Agency
from utils.forecast_logger import ForecastLogger


class ForecastPriorityScheduler:
    """重要な機関（優先度が高い・大規模）を先に巡回する順序付けを行う。"""

    PRIORITY_ORDER = {"高": 0, "中": 1, "低": 2}

    def __init__(self):
        self.logger = ForecastLogger("PriorityScheduler")

    def get_prioritized_agencies(self) -> List[Agency]:
        with get_db() as session:
            agencies = session.query(Agency).all()
            return sorted(
                agencies,
                key=lambda a: (self.PRIORITY_ORDER.get(a.priority_level or "低", 3), a.id),
            )

    def select_new_url_first(self, agencies: List[Agency]) -> List[Agency]:
        """未クロール（last_crawled_at が null）の機関を優先する。"""
        return sorted(
            agencies,
            key=lambda a: (0 if getattr(a, "last_crawled_at", None) is None else 1, a.id),
        )
