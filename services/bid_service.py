from typing import List, Dict, Any, Optional
from database.repositories.bid_repository import BidRepository
from database.repositories.favorite_repository import FavoriteRepository
from config import AppConfig


class BidService:
    """
    入札案件データの永続化およびビジネスロジックを管理するサービス。
    """
    def __init__(self, repository: BidRepository, favorite_repository: FavoriteRepository = None):
        self.repository = repository
        self.favorite_repository = favorite_repository

    def create_bid_entry(self, bid_data: Dict[str, Any]) -> Optional[int]:
        return self.repository.create(bid_data)

    def get_all_bids(self, filters: Optional[Dict[str, Any]] = None, allowed_prefectures: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        # 全案件を取得して辞書にマッピング
        db_bids = self.repository.list_all(limit=1000)
        bids = []
        scope = set(allowed_prefectures) if allowed_prefectures is not None else None
        for bid in db_bids:
            bid_dict = {
                "id": bid.id,
                "filename": bid.filename,
                "project_name": getattr(bid, "project_name", "不明") or "不明",
                "source_url": bid.source_url or "",
                "budget": bid.budget or "記載なし",
                "qualifications": bid.qualifications or "記載なし",
                "deadline": bid.deadline or "記載なし",
                "deliverables": bid.deliverables or "記載なし",
                "key_risks": bid.key_risks or "記載なし",
                "current_status": bid.current_status or "未確認",
                "industry_category": bid.industry_category or "不明",
                "organization_name": bid.organization_name or "不明",
                "budget_amount": bid.budget_amount,
                "prefecture_code": getattr(bid, "prefecture_code", None),
            }
            if scope is not None and bid_dict["prefecture_code"] not in scope:
                continue
            
            # フィルタ処理
            if filters:
                match = True
                for k, v in filters.items():
                    if v:
                        val = str(bid_dict.get(k, "")).lower()
                        if str(v).lower() not in val:
                            match = False
                            break
                if match:
                    bids.append(bid_dict)
            else:
                bids.append(bid_dict)
        return bids


    def list_favorites(self, user_id: str, filters: Optional[Dict[str, Any]] = None):
        if not self.favorite_repository:
            raise RuntimeError("favorite_repository is not configured")

        favorites = self.favorite_repository.get_favorites(user_id)
        bids = []
        for fav in favorites:
            bid = self.repository.get_by_id(fav.bid_id)
            if bid:
                bid_dict = {
                    "id": bid.id,
                    "filename": bid.filename,
                    "current_status": getattr(bid, "current_status", None),
                    "budget": getattr(bid, "budget", None),
                    "qualifications": getattr(bid, "qualifications", None),
                    "deadline": getattr(bid, "deadline", None),
                    "deliverables": getattr(bid, "deliverables", None),
                    "favorited_at": fav.favorited_at,
                    "memo": fav.memo or "",
                }
                if filters:
                    for k, v in filters.items():
                        if v and str(bid_dict.get(k, "")).find(v) == -1:
                            break
                    else:
                        bids.append(bid_dict)
                else:
                    bids.append(bid_dict)
        return bids

    def toggle_favorite(self, bid_id: int, user_id: str, memo: str = "") -> bool:
        if not self.favorite_repository:
            raise RuntimeError("favorite_repository is not configured")
        existing = self.favorite_repository.get_favorites(user_id)
        for fav in existing:
            if fav.bid_id == bid_id:
                self.favorite_repository.remove(bid_id, user_id)
                return False
        self.favorite_repository.add(bid_id=bid_id, user_id=user_id, memo=memo)
        return True
