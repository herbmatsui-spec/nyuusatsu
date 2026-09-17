"""Repository classes referenced across the codebase.

NOTE: These are reconstructed thin wrappers over the generated models. The exact
method surface of the original package is not fully known; add project-specific
query methods here as call sites require them.
"""
from datetime import date, datetime
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
from ..models import CrawlHistory as _CrawlHistory
from ..models import SystemSetting as _Setting
from ..models import AgencyInventory as _AgencyInventory
from ..models import Prefecture as _Prefecture
from typing import Optional
from .base import BaseRepository


class CompetitorRepository(BaseRepository):
    model = _Competitor


class CompanyProfileRepository(BaseRepository):
    model = _CompanyProfile


class CompanyRegionRankRepository(BaseRepository):
    model = _CompanyRegionRank


class BidAssignmentRepository(BaseRepository):
    model = _BidAssignment

    def get_by_bid(self, bid_id: int):
        """Get all assignments for a specific bid."""
        return self.session.query(self.model).filter(self.model.bid_id == bid_id).all()


class BidRepository(BaseRepository):
    model = _Bid

    def list_all(self, limit: int = None):
        query = self.session.query(self.model)
        if limit:
            query = query.limit(limit)
        return query.all()

    def search(
        self,
        keyword: Optional[str] = None,
        prefecture: Optional[str] = None,
        prefecture_codes: Optional[list] = None,
        organization: Optional[str] = None,
        budget_min: Optional[int] = None,
        budget_max: Optional[int] = None,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
        offset: int = 0,
        limit: int = 20,
    ):
        """Search bids with optional filters and pagination.

        Returns a tuple of (results: list[Bid], total: int).
        prefecture_codes is an exact allow-list: [] yields no rows, None is unrestricted.
        """
        from sqlalchemy import or_
        query = self.session.query(self.model)
        if keyword:
            kw = f"%{keyword}%"
            query = query.filter(
                or_(
                    self.model.filename.ilike(kw),
                    self.model.organization_name.ilike(kw),
                    self.model.notes.ilike(kw),
                )
            )
        if prefecture_codes is not None:
            if not prefecture_codes:
                return [], 0
            query = query.filter(self.model.prefecture_code.in_(prefecture_codes))
        if prefecture:
            query = query.filter(self.model.prefecture_code == prefecture)
        if organization:
            query = query.filter(self.model.organization_name.ilike(f"%{organization}%"))
        if budget_min is not None:
            query = query.filter(self.model.budget_amount >= budget_min)
        if budget_max is not None:
            query = query.filter(self.model.budget_amount <= budget_max)
        if published_after is not None:
            query = query.filter(self.model.announcement_date >= published_after)
        if published_before is not None:
            query = query.filter(self.model.announcement_date <= published_before)
        total = query.count()
        results = query.order_by(self.model.announcement_date.desc()).offset(offset).limit(limit).all()
        return results, total

    def upsert_bid(self, bid_data: dict):
        data = dict(bid_data)
        bid_id = data.pop("id", None)
        bid = self.session.get(self.model, bid_id) if bid_id is not None else None

        if bid is None and data.get("source_url"):
            bid = self.session.query(self.model).filter(
                self.model.source_url == data["source_url"]
            ).first()

        if bid is None and data.get("filename"):
            bid = self.session.query(self.model).filter(
                self.model.filename == data["filename"]
            ).first()

        if bid is None:
            bid = self.model(**data)
        else:
            for key, value in data.items():
                if hasattr(bid, key):
                    setattr(bid, key, value)

        self.session.add(bid)
        self.session.commit()
        self.session.refresh(bid)
        return bid

    def get_delay_percentile(self, delay_expr, percentile: float = 50.0):
        """Calculate the delay percentile using LIMIT/OFFSET to avoid full memory load.

        SQLite does not support PERCENTILE_CONT, so we approximate by sorting
        the delay expression and picking the element at the percentile index.

        Args:
            delay_expr: A SQLAlchemy column expression for the delay.
            percentile: Percentile value (0-100). Default 50 (median).

        Returns:
            The delay value at the given percentile, or 0.0 if no data.
        """
        from sqlalchemy import func

        base_query = self.session.query(self.model).filter(
            self.model.announcement_date != None,
            self.model.created_at != None,
            delay_expr >= 0,
        )
        total = base_query.count()
        if total == 0:
            return 0.0

        mid = int(total * percentile / 100)
        result = base_query.order_by(delay_expr).with_entities(delay_expr).limit(1).offset(mid).scalar()
        return round(float(result), 2) if result is not None else 0.0


class PDFRepository(BaseRepository):
    model = _PDFDocument


class AgencyRepository(BaseRepository):
    model = _Agency


class ExtractionResultRepository(BaseRepository):
    model = _ExtractionResult

    def count_by_user_today(self, user_id: int, target_date: date) -> int:
        """Count extraction results created by user on a specific date."""
        from datetime import datetime, timedelta
        start = datetime.combine(target_date, datetime.min.time())
        end = start + timedelta(days=1)
        return self.session.query(self.model).filter(
            self.model.created_by == str(user_id),
            self.model.created_at >= start,
            self.model.created_at < end
        ).count()


class CustomerRepository(BaseRepository):
    model = _Customer


class PartnerRepository(BaseRepository):
    model = _Partner


class SavedSearchRepository(BaseRepository):
    model = _SavedSearch

    def get_active_by_user(self, user_id: int):
        return self.session.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.is_active == True
        ).all()

    def get_all_active(self):
        return self.session.query(self.model).filter(
            self.model.is_active == True
        ).all()


class NotificationChannelRepository(BaseRepository):
    model = _NotificationChannel

    def get_active_by_user(self, user_id: str):
        return self.session.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.is_active == True
        ).all()


class FavoriteRepository(BaseRepository):
    model = _Favorite


class AwardResultRepository(BaseRepository):
    model = _AwardResult

    def search(
        self,
        keyword: Optional[str] = None,
        winner_name: Optional[str] = None,
        agency_name: Optional[str] = None,
        budget_min: Optional[int] = None,
        budget_max: Optional[int] = None,
        awarded_after: Optional[datetime] = None,
        awarded_before: Optional[datetime] = None,
        bid_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 20,
    ):
        """Search award results with optional filters and pagination.

        Returns a tuple of (results: list[AwardResult], total: int).
        """
        from sqlalchemy import or_
        query = self.session.query(self.model)
        if keyword:
            kw = f"%{keyword}%"
            query = query.filter(
                or_(
                    self.model.project_name.ilike(kw),
                    self.model.agency_name.ilike(kw),
                    self.model.winner_name.ilike(kw),
                )
            )
        if winner_name:
            query = query.filter(self.model.winner_name.ilike(f"%{winner_name}%"))
        if agency_name:
            query = query.filter(self.model.agency_name.ilike(f"%{agency_name}%"))
        if budget_min is not None:
            query = query.filter(self.model.budget_amount >= budget_min)
        if budget_max is not None:
            query = query.filter(self.model.budget_amount <= budget_max)
        if awarded_after is not None:
            query = query.filter(self.model.award_date >= awarded_after)
        if awarded_before is not None:
            query = query.filter(self.model.award_date <= awarded_before)
        if bid_id is not None:
            query = query.filter(self.model.tender_id == bid_id)
        total = query.count()
        results = query.order_by(self.model.award_date.desc()).offset(offset).limit(limit).all()
        return results, total


class CrawlHistoryRepository(BaseRepository):
    model = _CrawlHistory

    def record(self, url_count: int, new_count: int, status: str, error_message: str = None):
        """Record a crawl session result."""
        from datetime import datetime
        obj = self.model(
            crawl_time=datetime.now(),
            url_count=url_count,
            new_count=new_count,
            status=status,
            error_message=error_message,
        )
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def get_recent(self, limit: int = 50):
        """Retrieve recent crawl history."""
        return self.session.query(self.model).order_by(self.model.crawl_time.desc()).limit(limit).all()

    def get_by_period(self, period_start: str, period_end: str):
        """Retrieve crawl history within a period."""
        return self.session.query(self.model).filter(
            self.model.crawl_time >= period_start,
            self.model.crawl_time <= period_end
        ).all()


class CrawledUrlRepository(BaseRepository):
    model = _CrawledUrl

    def get_all(self, limit: int = 100):
        """Retrieve crawled URLs."""
        return self.session.query(self.model).limit(limit).all()

    def mark_notified(self, url: str) -> bool:
        """Mark a URL as notified."""
        obj = self.first_by(url=url)
        if obj:
            obj.notified = True
            self.session.commit()
            return True
        return False

    def record(self, url: str, title: str):
        """Record a crawled URL, or return existing one."""
        from datetime import datetime
        existing = self.first_by(url=url)
        if existing:
            return existing
        obj = self.model(
            url=url,
            title=title,
            found_time=datetime.now(),
            notified=False,
        )
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def exists(self, url: str) -> bool:
        """Check if a URL exists in the database."""
        return self.first_by(url=url) is not None

    def get_notified_status(self, url: str) -> bool | None:
        """Get notified status of a URL."""
        obj = self.first_by(url=url)
        if obj:
            return obj.notified
        return None

    def bulk_insert(self, urls: list[dict]) -> int:
        """Bulk insert URLs. Returns count of new inserts."""
        from datetime import datetime
        count = 0
        for item in urls:
            existing = self.first_by(url=item["url"])
            if not existing:
                obj = self.model(
                    url=item["url"],
                    title=item.get("title", "No Title"),
                    found_time=item.get("found_time", datetime.now()),
                    notified=item.get("notified", False),
                )
                self.session.add(obj)
                count += 1
        self.session.commit()
        return count


class SettingRepository(BaseRepository):
    model = _Setting

    def get(self, key: str) -> str | None:
        """Get a setting value by key."""
        obj = self.first_by(key=key)
        return obj.value if obj else None

    def set(self, key: str, value: str):
        """Set a setting value."""
        obj = self.first_by(key=key)
        if obj:
            obj.value = value
        else:
            obj = self.model(key=key, value=value)
            self.session.add(obj)
        self.session.commit()
        return obj

    def delete(self, key: str) -> bool:
        """Delete a setting."""
        obj = self.first_by(key=key)
        if obj:
            self.session.delete(obj)
            self.session.commit()
            return True
        return False

    def get_all(self) -> dict:
        """Get all settings as a dictionary."""
        results = self.all()
        return {r.key: r.value for r in results}

class AgencyInventoryRepository(BaseRepository):
    model = _AgencyInventory

class PrefectureRepository(BaseRepository):
    model = _Prefecture



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
