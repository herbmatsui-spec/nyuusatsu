"""URL registry repository."""
from ..models import UrlRegistry as _UrlRegistry
from .base import BaseRepository


class URLRegistryRepository(BaseRepository):
    model = _UrlRegistry
