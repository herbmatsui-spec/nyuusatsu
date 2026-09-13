#!/usr/bin/env python3
"""Example usage of dynamic crawl frequency adjustment system.

This script demonstrates how to integrate the crawl schedule
into your crawler logic.
"""
import logging
from datetime import datetime, timezone

from database.engine import get_session
from database.models import CrawlerSchedule, Agency, AgencyCategory


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_crawl_interval_for_agency(agency: Agency) -> int:
    """Get the current crawl interval for an agency based on its category and priority.

    Args:
        agency: Agency object with category_id and priority_level

    Returns:
        Interval in seconds
    """
    with get_session() as session:
        schedule = session.query(CrawlerSchedule).filter(
            CrawlerSchedule.category_id == agency.category_id,
            CrawlerSchedule.priority_level == agency.priority_level,
        ).first()

        if schedule:
            logger.info(
                "Using dynamic interval for agency %s (cat=%d, pri=%d): %ds",
                agency.name, agency.category_id, agency.priority_level,
                schedule.current_interval_seconds
            )
            return schedule.current_interval_seconds

        # Fallback to default based on priority
        defaults = {1: 1800, 2: 3600, 3: 7200, 4: 14400, 5: 28800}
        default = defaults.get(agency.priority_level, 3600)
        logger.warning(
            "No schedule found for agency %s (cat=%d, pri=%d), using default: %ds",
            agency.name, agency.category_id, agency.priority_level, default
        )
        return default


def get_all_schedules() -> list[dict]:
    """Get all current crawl schedules with category names.

    Returns:
        List of schedule dictionaries
    """
    with get_session() as session:
        schedules = session.query(CrawlerSchedule).all()
        result = []
        for s in schedules:
            cat = session.query(AgencyCategory).filter(
                AgencyCategory.id == s.category_id
            ).first()
            result.append({
                "category_id": s.category_id,
                "category_name": cat.name if cat else "Unknown",
                "priority_level": s.priority_level,
                "base_interval_seconds": s.base_interval_seconds,
                "current_interval_seconds": s.current_interval_seconds,
                "success_rate": s.success_rate,
                "last_updated": s.last_updated.isoformat() if s.last_updated else None,
            })
        return result


def simulate_crawl_result(agency: Agency, success: bool, response_time_ms: float = 0) -> None:
    """Simulate recording a crawl result (for testing).

    In production, this would be called by the actual crawler
    to record success/failure for the dynamic adjustment.

    Args:
        agency: The agency that was crawled
        success: Whether the crawl succeeded
        response_time_ms: Response time in milliseconds
    """
    # This would typically be handled by the crawler infrastructure
    # recording to CrawlLog or similar table
    from database.models._generated import CrawlLog

    with get_session() as session:
        log = CrawlLog(
            agency_id=agency.id,
            crawled_at=datetime.now(timezone.utc),
            status="success" if success else "failed",
            error_message=None if success else "Simulated error",
            new_bids_count=5 if success else 0,
        )
        session.add(log)
        session.commit()
        logger.info("Recorded crawl log for %s: %s", agency.name, "success" if success else "failed")


def main():
    """Demonstrate usage."""
    with get_session() as session:
        # Get all agencies
        agencies = session.query(Agency).all()

        print("=== Agency Crawl Intervals ===")
        for agency in agencies:
            interval = get_crawl_interval_for_agency(agency)
            cat = session.query(AgencyCategory).filter(
                AgencyCategory.id == agency.category_id
            ).first()
            cat_name = cat.name if cat else "Unknown"
            print(f"  {agency.name} ({cat_name}, priority={agency.priority_level}): {interval}s")

        print("\n=== All Schedules ===")
        schedules = get_all_schedules()
        for s in schedules:
            print(
                f"  {s['category_name']} (pri={s['priority_level']}): "
                f"base={s['base_interval_seconds']}s, "
                f"current={s['current_interval_seconds']}s, "
                f"success_rate={s['success_rate']:.2%}"
            )

        # Example: Simulate some crawl results
        print("\n=== Simulating crawl results ===")
        if agencies:
            simulate_crawl_result(agencies[0], True, 1500)
            simulate_crawl_result(agencies[0], True, 1200)
            simulate_crawl_result(agencies[0], False, 0)

        # Show updated schedules
        print("\n=== Schedules after simulation (run adjust script to update) ===")
        schedules = get_all_schedules()
        for s in schedules:
            print(
                f"  {s['category_name']} (pri={s['priority_level']}): "
                f"base={s['base_interval_seconds']}s, "
                f"current={s['current_interval_seconds']}s, "
                f"success_rate={s['success_rate']:.2%}"
            )


if __name__ == "__main__":
    main()