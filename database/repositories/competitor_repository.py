"""Competitor repository."""
from ..models import Competitor as _Competitor
from .base import BaseRepository


class CompetitorRepository(BaseRepository):
    model = _Competitor
