from datetime import datetime, date
from typing import Optional, Dict, Any
import re

from database.session import get_db
from database.models import Bid, Prefecture, BidSource

class BidStorageService:
    def save_bid(self, bid_data: dict) -> Bid:
        with get_db() as db:
            budget_text = bid_data.get("budget", "")
            budget_amount = self._extract_budget_amount(budget_text)
            
            # source_urlで重複チェック
            existing_bid = db.query(Bid).filter(
                Bid.source_url == bid_data.get("source_url")
            ).first()
            
            # announcement_dateをdate型に変換
            announcement_date = self._parse_announcement_date(bid_data.get("announcement_date"))
            
            if existing_bid:
                update_data = {
                    "filename": bid_data.get("title", "未取得")[:255],  # titleをfilenameとして保存
                    "organization_name": bid_data.get("organization"),
                    "budget": bid_data.get("budget"),
                    "budget_amount": budget_amount,
                    "deadline": bid_data.get("deadline"),
                    "source_url": bid_data.get("source_url"),
                    "prefecture_code": bid_data.get("prefecture_code"),
                    "industry_category": bid_data.get("project_name"),
                    "qualifications": bid_data.get("qualifications"),
                    "deliverables": bid_data.get("deliverables"),
                    "announcement_date": announcement_date,
                    "updated_at": datetime.utcnow(),
                }
                for key, value in update_data.items():
                    if value is not None:
                        setattr(existing_bid, key, value)
                db.flush()
                return existing_bid
            else:
                bid_entity = Bid(
                    filename=bid_data.get("title", "未取得")[:255],
                    organization_name=bid_data.get("organization", "未取得"),
                    budget=bid_data.get("budget", ""),
                    budget_amount=budget_amount,
                    deadline=bid_data.get("deadline", "未取得"),
                    source_url=bid_data.get("source_url"),
                    prefecture_code=bid_data.get("prefecture_code"),
                    industry_category=bid_data.get("project_name", "未取得"),
                    current_status=bid_data.get("current_status", "未処理"),
                    qualifications=bid_data.get("qualifications"),
                    deliverables=bid_data.get("deliverables"),
                    announcement_date=announcement_date,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    analyzed_at=datetime.utcnow(),
                )
                db.add(bid_entity)
                db.flush()
                return bid_entity
    
    def _extract_budget_amount(self, budget_text: str) -> Optional[int]:
        if not budget_text:
            return None
        numbers = re.findall(r'\d+', budget_text)
        if not numbers:
            return None
        try:
            return int(numbers[0])
        except ValueError:
            return None
    
    def _parse_announcement_date(self, date_str: Optional[str]) -> Optional[date]:
        """公告日文字列をdate型に変換"""
        if not date_str:
            return None
        try:
            # YYYY-MM-DD形式を想定
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None
    