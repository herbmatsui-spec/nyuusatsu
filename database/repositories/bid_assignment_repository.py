"""Bid assignment repository."""
from ..models import BidAssignment as _BidAssignment
from .base import BaseRepository


class BidAssignmentRepository(BaseRepository):
    model = _BidAssignment
