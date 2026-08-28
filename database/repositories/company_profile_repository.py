"""Company profile / region rank repositories."""
from ..models import CompanyProfile as _CompanyProfile
from ..models import CompanyRegionRank as _CompanyRegionRank
from .base import BaseRepository


class CompanyProfileRepository(BaseRepository):
    model = _CompanyProfile


class CompanyRegionRankRepository(BaseRepository):
    model = _CompanyRegionRank
