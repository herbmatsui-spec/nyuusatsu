from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from database.models.extraction_result import ExtractionResult


class MilestoneService:
    def __init__(self, session: Session):
        self.session = session

    def get_upcoming(self, days: int = 30, bid_id: Optional[int] = None) -> list[dict]:
        today = date.today()
        end = today + timedelta(days=days)
        query = self.session.query(ExtractionResult)

        if bid_id is not None:
            query = query.filter(ExtractionResult.bid_id == bid_id)

        results = []
        for ext in query.filter(
            ExtractionResult.question_deadline.isnot(None)
        ).all():
            d = ext.question_deadline
            if isinstance(d, datetime):
                d = d.date()
            if today <= d <= end:
                results.append({
                    "bid_id": ext.bid_id,
                    "filename": ext.filename,
                    "type": "質問回答期限",
                    "date": d,
                })

        for ext in query.filter(
            ExtractionResult.submit_deadline.isnot(None)
        ).all():
            d = ext.submit_deadline
            if isinstance(d, datetime):
                d = d.date()
            if today <= d <= end:
                results.append({
                    "bid_id": ext.bid_id,
                    "filename": ext.filename,
                    "type": "申請書提出期限",
                    "date": d,
                })

        for ext in query.filter(
            ExtractionResult.opening_date.isnot(None)
        ).all():
            d = ext.opening_date
            if isinstance(d, datetime):
                d = d.date()
            if today <= d <= end:
                results.append({
                    "bid_id": ext.bid_id,
                    "filename": ext.filename,
                    "type": "開札日",
                    "date": d,
                })

        results.sort(key=lambda x: x["date"])
        return results

    def get_by_bid(self, bid_id: int) -> list[dict]:
        return self.get_upcoming(days=9999, bid_id=bid_id)
