from sqlalchemy.orm import Session
from database.repositories.bid_repository import BidRepository
from database.models import Bid

class StatusService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = BidRepository(session)

    def change_status(self, bid_id: int, new_status: str, changed_by: str = "system", memo: str = "") -> bool:
        """
        ステータスを変更し、履歴を記録する。
        """
        bid = self.repo.get_by_id(bid_id)
        if not bid:
            return False

        # ステータス更新
        self.repo.update(bid, {"current_status": new_status})
        
        # 履歴保存
        self.repo.add_status_history(
            bid_id=bid_id,
            status=new_status,
            changed_by=changed_by,
            memo=memo
        )
        return True
