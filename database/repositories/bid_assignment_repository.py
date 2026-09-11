"""Bid assignment repository."""
from ..models import BidAssignment as _BidAssignment
from .base import BaseRepository


class BidAssignmentRepository(BaseRepository):
    model = _BidAssignment

    def get_by_bid(self, bid_id: int):
        """Get all assignments for a specific bid."""
        return self.session.query(self.model).filter(self.model.bid_id == bid_id).all()
