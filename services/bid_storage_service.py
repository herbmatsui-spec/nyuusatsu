from datetime import datetime, date, timezone
from typing import Optional

from database.session import get_session
from database.models import Bid
from services.extracted_fields_normalizer import normalize_budget, normalize_extracted_fields


class BidStorageService:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session

    def save_bid(self, bid_data: dict) -> Bid:
        fields = normalize_extracted_fields(bid_data)
        with self.session_factory() as db:
            try:
                source_url = bid_data.get("source_url")
                existing_bid = db.query(Bid).filter(Bid.source_url == source_url).first() if source_url else None
                announcement_date = self._parse_announcement_date(bid_data.get("announcement_date"))
                now = datetime.now(timezone.utc)
                if existing_bid:
                    update_data = {
                        "filename": bid_data.get("title", "未取得")[:255],
                        "organization_name": bid_data.get("organization"),
                        "source_url": source_url,
                        "prefecture_code": bid_data.get("prefecture_code"),
                        "industry_category": bid_data.get("project_name"),
                        "announcement_date": announcement_date,
                        "updated_at": now,
                    }
                    for key, value in update_data.items():
                        if value is not None:
                            setattr(existing_bid, key, value)
                    failed = bid_data.get("success") is False or bid_data.get("error") or bid_data.get("status") in ("failed", "error")
                    for key, value in fields.items():
                        supplied = key in bid_data
                        if key in ("budget", "budget_amount"):
                            supplied = supplied or "budget" in bid_data or "budget_amount" in bid_data
                        if key == "delivery_deadline":
                            supplied = supplied or "deadline" in bid_data
                        if supplied or failed:
                            setattr(existing_bid, key, value)
                    bid_entity = existing_bid
                else:
                    bid_entity = Bid(
                        filename=bid_data.get("title", "未取得")[:255],
                        organization_name=bid_data.get("organization", "未取得"),
                        source_url=source_url,
                        prefecture_code=bid_data.get("prefecture_code"),
                        industry_category=bid_data.get("project_name", "未取得"),
                        current_status=bid_data.get("current_status", "未処理"),
                        announcement_date=announcement_date,
                        created_at=now,
                        updated_at=now,
                        analyzed_at=now,
                        **fields,
                    )
                    db.add(bid_entity)
                db.flush()
                db.commit()
                db.refresh(bid_entity)
                db.expunge(bid_entity)
                return bid_entity
            except Exception:
                db.rollback()
                raise

    def _extract_budget_amount(self, budget_text: str) -> Optional[int]:
        return normalize_budget(budget_text)

    def _parse_announcement_date(self, date_str: Optional[str]) -> Optional[date]:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None
