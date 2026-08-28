"""Repository classes referenced across the codebase.

NOTE: These are reconstructed thin wrappers over the generated models. The exact
method surface of the original package is not fully known; add project-specific
query methods here as call sites require them.
"""
from ..models import AwardResult as _AwardResult
from ..models import Bid as _Bid
from ..models import Agency as _Agency
from ..models import PDFDocument as _PDFDocument
from ..models import ExtractionResult as _ExtractionResult
from ..models import Customer as _Customer
from ..models import Partner as _Partner
from ..models import SavedSearch as _SavedSearch
from ..models import NotificationChannel as _NotificationChannel
from ..models import Favorite as _Favorite
from ..models import Competitor as _Competitor
from ..models import CompanyProfile as _CompanyProfile
from ..models import CompanyRegionRank as _CompanyRegionRank
from ..models import BidAssignment as _BidAssignment
from ..models import UrlRegistry as _UrlRegistry
from ..models import CrawledUrl as _CrawledUrl
from .base import BaseRepository


class CompetitorRepository(BaseRepository):
    model = _Competitor


class CompanyProfileRepository(BaseRepository):
    model = _CompanyProfile


class CompanyRegionRankRepository(BaseRepository):
    model = _CompanyRegionRank


class BidAssignmentRepository(BaseRepository):
    model = _BidAssignment


class BidRepository(BaseRepository):
    model = _Bid


class PDFRepository(BaseRepository):
    model = _PDFDocument


class AgencyRepository(BaseRepository):
    model = _Agency


class ExtractionResultRepository(BaseRepository):
    model = _ExtractionResult


class CustomerRepository(BaseRepository):
    model = _Customer


class PartnerRepository(BaseRepository):
    model = _Partner


class SavedSearchRepository(BaseRepository):
    model = _SavedSearch


class NotificationChannelRepository(BaseRepository):
    model = _NotificationChannel


class FavoriteRepository(BaseRepository):
    model = _Favorite


class AwardResultRepository(BaseRepository):
    model = _AwardResult


def save_bid(session, bid_data: dict, full_text: str = None):
    """Insert or update a single bid row from a dict."""
    bid = _Bid(**bid_data)
    session.add(bid)
    session.commit()
    session.refresh(bid)
    return bid


def save_bids_batch(session, records: list, texts: list = None):
    """Bulk insert bid rows. ``texts`` aligns with ``records`` when provided."""
    objs = []
    for i, rec in enumerate(records):
        data = dict(rec)
        if texts and i < len(texts) and texts[i] is not None:
            pass
        objs.append(_Bid(**data))
    session.add_all(objs)
    session.commit()
    return objs


def get_active_agency_urls(session):
    """Return active agency URL records (objects exposing ``.id`` and ``.base_url``)."""
    return session.query(_UrlRegistry).filter(
        _UrlRegistry.base_url.isnot(None), _UrlRegistry.base_url != ""
    ).all()


def save_url_probe_log(session, agency_id, status: str, error: str = None):
    """Persist a URL probe result as a crawled-url log entry."""
    log = _CrawledUrl(url=str(agency_id), title=status or "", found_time=None, notified=False)
    session.add(log)
    session.commit()
    return log
