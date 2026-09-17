import argparse
import logging
from pathlib import Path
from typing import Callable, Dict

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from database.models import Bid
from services.extracted_fields_normalizer import normalize_extracted_fields

logger = logging.getLogger(__name__)


def backfill_extracted_fields(session_factory: Callable[[], Session], batch_size: int = 100, dry_run: bool = True) -> Dict[str, int]:
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    counts = {"scanned": 0, "changed": 0}
    with session_factory() as session:
        upper_id = session.query(func.max(Bid.id)).scalar()
    last_id = 0
    while upper_id is not None and last_id < upper_id:
        with session_factory() as session:
            try:
                bids = session.query(Bid).filter(Bid.id > last_id, Bid.id <= upper_id).order_by(Bid.id).limit(batch_size).all()
                if not bids:
                    break
                for bid in bids:
                    data = {
                        "budget": bid.budget if bid.budget is not None else bid.budget_amount,
                        "deadline": bid.deadline,
                        "qualifications": bid.qualifications,
                        "deliverables": bid.deliverables,
                    }
                    if bid.delivery_deadline is not None:
                        data["delivery_deadline"] = bid.delivery_deadline
                    fields = normalize_extracted_fields(data)
                    changed = {key: value for key, value in fields.items() if getattr(bid, key) != value}
                    if changed:
                        counts["changed"] += 1
                        if not dry_run:
                            for key, value in changed.items():
                                setattr(bid, key, value)
                    counts["scanned"] += 1
                    last_id = bid.id
                if not dry_run:
                    session.commit()
            except Exception:
                session.rollback()
                logger.exception("Extraction backfill batch rolled back")
                raise
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    path = args.database.resolve()
    if not path.is_file():
        parser.error("database must be an existing SQLite file with the step-1 schema")
    if not 1 <= args.batch_size <= 1000:
        parser.error("batch-size must be between 1 and 1000")
    logging.basicConfig(level=logging.INFO)
    mode = "rw" if args.apply else "ro"
    engine = create_engine(f"sqlite:///file:{path.as_posix()}?mode={mode}&uri=true")
    try:
        counts = backfill_extracted_fields(sessionmaker(bind=engine), args.batch_size, dry_run=not args.apply)
        logger.info("Backfill complete: %s; applied=%s", counts, args.apply)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
