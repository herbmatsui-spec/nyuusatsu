from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models.bid import Bid
from database.models.bid_assignment import BidAssignment
from database.repositories.bid_assignment_repository import BidAssignmentRepository
from config import AppConfig


class KanbanService:
    def __init__(self, session: Session):
        self.session = session
        self.config = AppConfig()
        self.assignment_repo = BidAssignmentRepository(session)

    def move_card(self, bid_id: int, new_status: str, user_id: str) -> Bid:
        bid = self.session.get(Bid, bid_id)
        if not bid:
            raise ValueError(f"Bid {bid_id} not found")
        if new_status not in self.config.kanban.columns:
            raise ValueError(f"Invalid kanban status: {new_status}")
        bid.current_status = new_status
        self.session.add(bid)
        self.session.flush()
        return bid

    def get_board(self, user_id: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        board: Dict[str, List[Dict[str, Any]]] = {col: [] for col in self.config.kanban.columns}
        bids = self.session.query(Bid).all()
        for bid in bids:
            status = bid.current_status or "未確認"
            if status not in board:
                status = "未確認"
            assignments = self.assignment_repo.get_by_bid(bid.id)
            assignees = [a.user_id for a in assignments if a.user_id]
            board[status].append({
                "id": bid.id,
                "filename": bid.filename,
                "organization_name": bid.organization_name,
                "budget": bid.budget,
                "assignees": assignees,
            })
        return board

    def assign_user(self, bid_id: int, user_id: str, role: str = "member") -> BidAssignment:
        return self.assignment_repo.create(
            bid_id=bid_id,
            user_id=user_id,
            role=role,
            assigned_at=datetime.utcnow(),
        )

    def unassign_user(self, bid_id: int, user_id: str) -> None:
        assignments = self.assignment_repo.get_by_bid(bid_id)
        for a in assignments:
            if a.user_id == user_id:
                self.session.delete(a)
        self.session.flush()
