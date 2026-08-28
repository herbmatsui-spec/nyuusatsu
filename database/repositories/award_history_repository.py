"""Award history repository."""
from ..models import AwardHistory as _AwardHistory
from .base import BaseRepository


class AwardHistoryRepository(BaseRepository):
    model = _AwardHistory
