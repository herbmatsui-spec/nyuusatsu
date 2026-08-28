from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from database.models.procurement_forecast import ProcurementForecast
from database.models.forecast_status import ForecastStatusEnum
from utils.notifier import Notifier
from utils.forecast_logger import ForecastLogger


class ForecastNotificationService:
    """新規発注見通し発見時の通知（メール等）を行う。"""

    def __init__(self, session: Optional[Session] = None, notifier: Optional[Notifier] = None):
        self.session = session
        self.notifier = notifier or Notifier()
        self.logger = ForecastLogger("Notification")

    def notify_new_forecasts(self, forecasts: List[ProcurementForecast]):
        if not forecasts:
            return
        lines = [f"新着発注見通し {len(forecasts)} 件を検出しました。\n"]
        for f in forecasts:
            lines.append(f"- {f.fiscal_year}年度 {f.title} ({f.category or '—'}) 予算: {f.estimated_budget or '—'}")
        body = "\n".join(lines)
        subject = f"【発注見通し】新着 {len(forecasts)} 件"
        self.notifier.send_notification(subject, body)

    def notify_crawl_summary(self, summary: Dict[str, Any]):
        body = (
            f"発注見通し巡回を実行しました。\n"
            f"実行時刻: {summary.get('finished_at')}\n"
            f"保存件数: {summary.get('total_stored', 0)} 件\n"
        )
        self.notifier.send_notification("【発注見通し】巡回完了", body)
