import argparse
import calendar
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from database.models import Bid
from services.bid_difficulty_scorer import BidDifficultyScorer

logger = logging.getLogger(__name__)


def _validate_options(months: int, batch_size: int, limit: int | None) -> None:
    if type(months) is not int or not 1 <= months <= 120:
        raise ValueError("months must be between 1 and 120")
    if type(batch_size) is not int or not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit must be a positive integer")


def _update_scores(
    session_factory: Callable[[], Session],
    score_factory: Callable[[Session], Callable[[Bid], float]],
    column: str,
    maximum: float,
    *,
    months: int = 24,
    batch_size: int = 100,
    limit: int | None = None,
    dry_run: bool = True,
    now: datetime | None = None,
) -> dict[str, int]:
    _validate_options(months, batch_size, limit)
    end = now if now is not None else datetime.now(timezone.utc)
    if end.tzinfo is not None:
        end = end.astimezone(timezone.utc).replace(tzinfo=None)
    year, month = divmod(end.year * 12 + end.month - 1 - months, 12)
    month += 1
    start = end.replace(year=year, month=month, day=min(end.day, calendar.monthrange(year, month)[1]))
    filters = (Bid.announcement_date >= start, Bid.announcement_date <= end)
    counts = {"scanned": 0, "changed": 0, "updated": 0, "batches": 0}
    with session_factory() as session:
        upper_id = session.query(func.max(Bid.id)).filter(*filters).scalar()
    last_id = None
    while upper_id is not None and (limit is None or counts["scanned"] < limit):
        size = batch_size if limit is None else min(batch_size, limit - counts["scanned"])
        with session_factory() as session:
            try:
                with session.no_autoflush:
                    query = session.query(Bid).filter(*filters, Bid.id <= upper_id)
                    if last_id is not None:
                        query = query.filter(Bid.id > last_id)
                    bids = query.order_by(Bid.id).limit(size).all()
                    if not bids:
                        session.rollback()
                        break
                    score = score_factory(session)
                    updates = []
                    for bid in bids:
                        value = float(score(bid))
                        if not math.isfinite(value) or not 0 <= value <= maximum:
                            raise ValueError(f"Invalid {column} for bid {bid.id}: {value}")
                        if getattr(bid, column) != value:
                            updates.append({"id": bid.id, column: value})
                    next_id = bids[-1].id
                    batch_count = len(bids)
                if dry_run:
                    session.rollback()
                else:
                    if updates:
                        session.bulk_update_mappings(Bid, updates)
                    session.commit()
            except Exception:
                session.rollback()
                logger.exception("Score batch rolled back after bid %s; completed=%s", last_id, counts)
                raise
        last_id = next_id
        counts["scanned"] += batch_count
        counts["changed"] += len(updates)
        counts["updated"] += 0 if dry_run else len(updates)
        counts["batches"] += 1
        logger.info("%s: %s; dry_run=%s", column, counts, dry_run)
        if last_id >= upper_id:
            break
    return counts


def update_bid_difficulty_scores(
    session_factory: Callable[[], Session],
    *,
    months: int = 24,
    batch_size: int = 100,
    limit: int | None = None,
    dry_run: bool = True,
    now: datetime | None = None,
) -> dict[str, int]:
    def score_factory(session: Session) -> Callable[[Bid], float]:
        scorer = BidDifficultyScorer(session)
        return lambda bid: scorer.score(bid)["score"]

    return _update_scores(
        session_factory, score_factory, "bid_difficulty_score", 100.0,
        months=months, batch_size=batch_size, limit=limit, dry_run=dry_run, now=now,
    )


def _run_cli(job: Callable[..., dict[str, int]], description: str, argv: list[str] | None) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--months", type=int, default=24, help="Recent announcement lookback, 1-120 months (default: 24); unknown/future dates excluded")
    parser.add_argument("--batch-size", type=int, default=100, help="Rows per atomic transaction, 1-1000 (default: 100); earlier batches survive failure")
    parser.add_argument("--limit", type=int, default=None, help="Maximum bids to scan, in ascending ID order")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Calculate without writes (default)")
    mode.add_argument("--apply", action="store_true", help="Persist each successful batch using DATABASE_URL")
    args = parser.parse_args(argv)
    try:
        _validate_options(args.months, args.batch_size, args.limit)
    except ValueError as exc:
        parser.error(str(exc))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    from database.engine import get_session

    try:
        counts = job(
            get_session, months=args.months, batch_size=args.batch_size,
            limit=args.limit, dry_run=not args.apply,
        )
    except Exception:
        logger.exception("Score update failed; earlier committed batches remain")
        return 1
    logger.info("Complete: %s; dry_run=%s", counts, not args.apply)
    return 0


def main(argv: list[str] | None = None) -> int:
    return _run_cli(update_bid_difficulty_scores, "Precompute recent bid difficulty scores (0-100)", argv)


if __name__ == "__main__":
    sys.exit(main())
