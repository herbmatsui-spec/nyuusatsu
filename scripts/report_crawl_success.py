#!/usr/bin/env python3
"""Crawl success rate monitoring report script.

Generates success rate reports per category and priority level
from crawl history data.
"""
import argparse
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, and_

from database.engine import get_session
from database.models import CrawlerSchedule, AgencyCategory, Agency
from database.models._generated import CrawlLog, BackfillJob, BackfillJobStatus

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_HOURS = 24


def calculate_success_rate(
    session, category_id: int, priority_level: int, hours: int = DEFAULT_LOOKBACK_HOURS
) -> dict:
    """Calculate success rate and stats for a category/priority combination.

    Returns:
        dict with total_attempts, successful_attempts, success_rate, avg_response_time
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
        return {
            "total_attempts": 0,
            "successful_attempts": 0,
            "success_rate": 1.0,
            "avg_response_time_ms": 0.0,
            "failed_attempts": 0,
        }

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
        failed = total - successful

        return {
            "total_attempts": total,
            "successful_attempts": successful,
            "success_rate": successful / total if total > 0 else 1.0,
            "avg_response_time_ms": 0.0,
            "failed_attempts": failed,
        }

    total = len(crawl_logs)
    successful = sum(1 for log in crawl_logs if log.status == "success")
    failed = total - successful

    return {
        "total_attempts": total,
        "successful_attempts": successful,
        "success_rate": successful / total if total > 0 else 1.0,
        "avg_response_time_ms": 0.0,
        "failed_attempts": failed,
    }


def generate_report(
    session, hours: int = DEFAULT_LOOKBACK_HOURS, output_file: Optional[str] = None
) -> str:
    """Generate success rate report.

    Args:
        session: Database session
        hours: Lookback period in hours
        output_file: Optional file path to write report

    Returns:
        Report string
    """
    categories = session.query(AgencyCategory).all()
    priorities = [1, 2, 3, 4, 5]

    lines = []
    lines.append("=" * 80)
    lines.append(f"CRAWL SUCCESS RATE REPORT (Last {hours} hours)")
    lines.append(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append("=" * 80)
    lines.append("")

    header = f"{'Category':<12} {'Priority':>8} {'Attempts':>10} {'Success':>8} {'Failed':>8} {'Rate':>8} {'Schedule Interval':>18}"
    lines.append(header)
    lines.append("-" * len(header))

    total_attempts = 0
    total_success = 0
    total_failed = 0

    for category in categories:
        for priority in priorities:
            stats = calculate_success_rate(session, category.id, priority, hours)

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

            interval_str = f"{schedule.current_interval_seconds}s" if schedule else "N/A"

            line = (
                f"{category.name:<12} {priority:>8} "
                f"{stats['total_attempts']:>10} {stats['successful_attempts']:>8} "
                f"{stats['failed_attempts']:>8} {stats['success_rate']:>7.2%} "
                f"{interval_str:>18}"
            )
            lines.append(line)

            total_attempts += stats["total_attempts"]
            total_success += stats["successful_attempts"]
            total_failed += stats["failed_attempts"]

    lines.append("-" * len(header))
    overall_rate = total_success / total_attempts if total_attempts > 0 else 1.0
    lines.append(
        f"{'TOTAL':<12} {'':>8} {total_attempts:>10} {total_success:>8} "
        f"{total_failed:>8} {overall_rate:>7.2%} {'':>18}"
    )
    lines.append("")

    lines.append("SCHEDULE DETAILS:")
    lines.append("-" * 80)
    schedule_header = f"{'Category':<12} {'Priority':>8} {'Base Interval':>14} {'Current Interval':>16} {'Success Rate':>12} {'Last Updated':>25}"
    lines.append(schedule_header)
    lines.append("-" * len(schedule_header))

    schedules = session.query(CrawlerSchedule).all()
    for s in schedules:
        cat = session.query(AgencyCategory).filter(AgencyCategory.id == s.category_id).first()
        cat_name = cat.name if cat else "Unknown"
        lines.append(
            f"{cat_name:<12} {s.priority_level:>8} "
            f"{s.base_interval_seconds:>14}s {s.current_interval_seconds:>16}s "
            f"{s.success_rate:>11.2%} {s.last_updated.isoformat():>25}"
        )

    report = "\n".join(lines)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info("Report written to %s", output_file)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate crawl success rate report")
    parser.add_argument(
        "--hours", type=int, default=DEFAULT_LOOKBACK_HOURS, help="Lookback period in hours"
    )
    parser.add_argument("--output", "-o", type=str, help="Output file path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    with get_session() as session:
        if args.json:
            import json

            categories = session.query(AgencyCategory).all()
            priorities = [1, 2, 3, 4, 5]

            data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "lookback_hours": args.hours,
                "categories": [],
            }

            for category in categories:
                cat_data = {
                    "category_id": category.id,
                    "category_name": category.name,
                    "priorities": [],
                }
                for priority in priorities:
                    stats = calculate_success_rate(session, category.id, priority, args.hours)

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

                    cat_data["priorities"].append(
                        {
                            "priority": priority,
                            "stats": stats,
                            "schedule": {
                                "base_interval_seconds": schedule.base_interval_seconds if schedule else None,
                                "current_interval_seconds": schedule.current_interval_seconds if schedule else None,
                                "success_rate": schedule.success_rate if schedule else None,
                                "last_updated": schedule.last_updated.isoformat() if schedule else None,
                            }
                            if schedule
                            else None,
                        }
                    )

                data["categories"].append(cat_data)

            output = json.dumps(data, ensure_ascii=False, indent=2)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output)
                logger.info("JSON report written to %s", args.output)
            else:
                print(output)
        else:
            report = generate_report(session, args.hours, args.output)
            if not args.output:
                print(report)


if __name__ == "__main__":
    main()