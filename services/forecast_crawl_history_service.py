from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models.crawl_log import CrawlLog
from utils.forecast_logger import ForecastLogger


class ForecastCrawlHistoryService:
    """発注見通し巡回の結果・エラーを記録・追跡する。"""

    def __init__(self, session: Session):
        self.session = session
        self.logger = ForecastLogger("CrawlHistory")

    def record_run(self, agency_id: int, new_count: int, status: str, error: Optional[str] = None) -> CrawlLog:
        log = CrawlLog(
            agency_id=agency_id,
            crawled_at=datetime.utcnow(),
            status=status,
            error_message=error,
            new_bids_count=new_count,
            crawl_type="forecast",
        )
        self.session.add(log)
        self.session.commit()
        return log

    def get_recent(self, limit: int = 50) -> List[CrawlLog]:
        return (
            self.session.query(CrawlLog)
            .filter(CrawlLog.crawl_type == "forecast")
            .order_by(desc(CrawlLog.crawled_at))
            .limit(limit)
            .all()
        )

    def get_errors(self, limit: int = 20) -> List[CrawlLog]:
        return (
            self.session.query(CrawlLog)
            .filter(CrawlLog.crawl_type == "forecast", CrawlLog.status == "error")
            .order_by(desc(CrawlLog.crawled_at))
            .limit(limit)
            .all()
        )
