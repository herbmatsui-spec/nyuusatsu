import logging
from datetime import datetime
from typing import Optional

from database.engine import get_session, engine
from database.models import CrawlHistory, CrawledUrl
from database.repositories import (
    CrawlHistoryRepository,
    CrawledUrlRepository,
    SettingRepository,
)

logger = logging.getLogger(__name__)

def init_db(eng=None):
    """Initialize the database using SQLAlchemy engine."""
    if eng is None:
        eng = engine
    with get_session() as session:
        # Tables are already created via Alembic migrations
        logger.info("Database initialized successfully.")


# --- CrawlHistory (delegated to repository) ---


def record_crawl_history(url_count, new_count, status, error_message=None):
    """Record the result of a crawl session using SQLAlchemy ORM."""
    with get_session() as session:
        repo = CrawlHistoryRepository(session)
        return repo.record(url_count, new_count, status, error_message)


def get_crawl_history(limit=50):
    """Retrieve recent crawl history using SQLAlchemy ORM."""
    with get_session() as session:
        repo = CrawlHistoryRepository(session)
        records = repo.get_recent(limit)
        return [
            {
                "id": r.id,
                "crawl_time": r.crawl_time,
                "url_count": r.url_count,
                "new_count": r.new_count,
                "status": r.status,
                "error_message": r.error_message,
            }
            for r in records
        ]


# --- CrawledUrl (delegated to repository) ---


def get_crawled_urls(limit=100):
    """Retrieve crawled URLs using SQLAlchemy ORM."""
    with get_session() as session:
        repo = CrawledUrlRepository(session)
        records = repo.get_all(limit)
        return [
            {
                "id": r.id,
                "url": r.url,
                "title": r.title,
                "found_time": r.found_time,
                "notified": r.notified,
            }
            for r in records
        ]


def mark_url_notified(url):
    """Mark a URL as notified."""
    with get_session() as session:
        repo = CrawledUrlRepository(session)
        return repo.mark_notified(url)


def record_crawled_url(url, title):
    """Record a crawled URL."""
    with get_session() as session:
        repo = CrawledUrlRepository(session)
        return repo.record(url, title)


# --- Setting (delegated to repository) ---


def get_setting(key: str) -> Optional[str]:
    """Get a setting value."""
    with get_session() as session:
        repo = SettingRepository(session)
        return repo.get(key)


def set_setting(key: str, value: str):
    """Set a setting value."""
    with get_session() as session:
        repo = SettingRepository(session)
        return repo.set(key, value)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
