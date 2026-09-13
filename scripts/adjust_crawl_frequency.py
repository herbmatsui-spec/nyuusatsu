#!/usr/bin/env python3
"""Dynamic crawl frequency adjustment script.

Collects success rates from crawl history and adjusts crawl intervals
per category and priority level.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, and_

from database.engine import get_session
from database.models import CrawlerSchedule, AgencyCategory, Agency
from database.models._generated import CrawlLog, BackfillJob, BackfillJobStatus

logger = logging.getLogger(__name__)


DEFAULT_BASE_INTERVAL = 3600
MIN_INTERVAL = 300
MAX_INTERVAL = 86400
TARGET_SUCCESS_RATE = 0.95
LOOKBACK_HOURS = 24


def get_default_base_interval(priority_level: int) -> int:
    """Get default base interval based on priority level."""
    intervals = {
        1: 1800,
        2: 3600,
        3: 7200,
        4: 14400,
        5: 28800,
    }
    return intervals.get(priority_level, DEFAULT_BASE_INTERVAL)


def calculate_success_rate(
    session, category_id: int, priority_level: int, hours: int = LOOKBACK_HOURS
) -> tuple[int, int, float]:
    """Calculate success rate for a category/priority combination.

    Returns:
        tuple: (total_attempts, successful_attempts, success_rate)
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    agency_ids = [
        a.id
        for a in session.query(Agency.id)
        .filter(
            and_(
                Agency.category_id == category_id,
                Agency.priority_level == priority_level,
            )
        )
        .all()
    ]

    if not agency_ids:
        return 0, 0, 1.0

    crawl_logs = (
        session.query(CrawlLog)
        .filter(
            and_(
                CrawlLog.agency_id.in_(agency_ids),
                CrawlLog.crawled_at >= since,
            )
        )
        .all()
    )

    if not crawl_logs:
        backfill_jobs = (
            session.query(BackfillJob)
            .filter(
                and_(
                    BackfillJob.agency_id.in_(agency_ids),
                    BackfillJob.started_at >= since,
                    BackfillJob.status.in_([BackfillJobStatus.DONE, BackfillJobStatus.FAILED]),
                )
            )
            .all()
        )

        total = len(backfill_jobs)
        successful = sum(1 for j in backfill_jobs if j.status == BackfillJobStatus.DONE)
        return total, successful, successful / total if total > 0 else 1.0

    total = len(crawl_logs)
    successful = sum(1 for log in crawl_logs if log.status == "success")
    return total, successful, successful / total if total > 0 else 1.0


def adjust_interval(
    base_interval: int, current_interval: int, success_rate: float, target_rate: float = TARGET_SUCCESS_RATE
) -> int:
    """Calculate new interval based on success rate.

    Formula: new_interval = base_interval * (target_rate / actual_success_rate)
    """
    if success_rate <= 0:
        return min(current_interval * 2, MAX_INTERVAL)

    ratio = target_rate / success_rate
    new_interval = int(base_interval * ratio)

    return max(MIN_INTERVAL, min(new_interval, MAX_INTERVAL))


def upsert_schedule(
    session, category_id: int, priority_level: int, base_interval: int, current_interval: int, success_rate: float
) -> CrawlerSchedule:
    """Insert or update crawler schedule."""
    schedule = (
        session.query(CrawlerSchedule)
        .filter(
            and_(
                CrawlerSchedule.category_id == category_id,
                CrawlerSchedule.priority_level == priority_level,
            )
        )
        .first()
    )

    if schedule:
        schedule.base_interval_seconds = base_interval
        schedule.current_interval_seconds = current_interval
        schedule.success_rate = success_rate
        schedule.last_updated = datetime.now(timezone.utc)
    else:
        schedule = CrawlerSchedule(
            category_id=category_id,
            priority_level=priority_level,
            base_interval_seconds=base_interval,
            current_interval_seconds=current_interval,
            success_rate=success_rate,
            last_updated=datetime.now(timezone.utc),
        )
        session.add(schedule)

    return schedule


def initialize_default_schedules(session) -> None:
    """Initialize default schedules for all category/priority combinations."""
    categories = session.query(AgencyCategory).all()
    priorities = [1, 2, 3, 4, 5]

    for category in categories:
        for priority in priorities:
            existing = (
                session.query(CrawlerSchedule)
                .filter(
                    and_(
                        CrawlerSchedule.category_id == category.id,
                        CrawlerSchedule.priority_level == priority,
                    )
                )
                .first()
            )

            if not existing:
                base_interval = get_default_base_interval(priority)
                schedule = CrawlerSchedule(
                    category_id=category.id,
                    priority_level=priority,
                    base_interval_seconds=base_interval,
                    current_interval_seconds=base_interval,
                    success_rate=1.0,
last_updated=datetime.now(timezone.utc),
                )
                session.add(schedule)
                logger.info(
                    "Initialized schedule: category=%s, priority=%d, interval=%ds",
                    category.name,
                    priority,
                    base_interval,
                )

    session.commit()


def main() -> None:
    """Main entry point for crawl frequency adjustment."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting crawl frequency adjustment")

    with get_session() as session:
        initialize_default_schedules(session)

        categories = session.query(AgencyCategory).all()
        priorities = [1, 2, 3, 4, 5]

        for category in categories:
            for priority in priorities:
                total, successful, success_rate = calculate_success_rate(
                    session, category.id, priority
                )

                base_interval = get_default_base_interval(priority)

                schedule = (
                    session.query(CrawlerSchedule)
                    .filter(
                        and_(
                            CrawlerSchedule.category_id == category.id,
                            CrawlerSchedule.priority_level == priority,
                        )
                    )
                    .first()
                )

                current_interval = schedule.current_interval_seconds if schedule else base_interval
                new_interval = adjust_interval(base_interval, current_interval, success_rate)

                upsert_schedule(
                    session,
                    category.id,
                    priority,
                    base_interval,
                    new_interval,
                    success_rate,
                )

                logger.info(
                    "Adjusted: category=%s, priority=%d, attempts=%d, successes=%d, "
                    "success_rate=%.2f%%, interval=%ds -> %ds",
                    category.name,
                    priority,
                    total,
                    successful,
                    success_rate * 100,
                    current_interval,
                    new_interval,
                )

        session.commit()
        logger.info("Crawl frequency adjustment completed")

        schedules = session.query(CrawlerSchedule).all()
        print("\n=== Current Crawler Schedules ===")
        for s in schedules:
            cat = session.query(AgencyCategory).filter(AgencyCategory.id == s.category_id).first()
            cat_name = cat.name if cat else "Unknown"
            print(
                f"  Category: {cat_name} (ID: {s.category_id}), "
                f"Priority: {s.priority_level}, "
                f"Base: {s.base_interval_seconds}s, "
                f"Current: {s.current_interval_seconds}s, "
                f"Success Rate: {s.success_rate:.2%}, "
                f"Updated: {s.last_updated}"
            )


if __name__ == "__main__":
    main()