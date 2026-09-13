import logging
from database.session import get_session
from database.repositories import CrawledUrlRepository

logger = logging.getLogger(__name__)


def detect_new_bids(new_urls_list):
    """
    Compare new_urls_list with the database to find bids that haven't been notified.
    new_urls_list: list of dicts [{'url': '...', 'title': '...'}]
    Returns: list of new bids and total count.
    """
    with get_session() as session:
        repo = CrawledUrlRepository(session)
        new_bids = []

        for bid in new_urls_list:
            url = bid['url']
            title = bid.get('title', 'No Title')

            # Check if URL already exists in crawled_urls
            existing = repo.get_notified_status(url)

            if existing is None:
                # It's a new bid
                repo.record(url, title)
                new_bids.append(bid)
            elif not existing:
                # Exists but not notified
                new_bids.append(bid)

        return new_bids


def mark_as_notified(urls):
    """Mark specific URLs as notified in the database."""
    with get_session() as session:
        repo = CrawledUrlRepository(session)
        for url in urls:
            repo.mark_notified(url)
