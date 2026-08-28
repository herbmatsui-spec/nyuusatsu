"""
Normalize Competitors
competitors テーブル内の全レコードの正規名を再計算し、
重複しているものを統合する。
"""
import logging
import sys

sys.path.insert(0, ".")

from database.engine import get_session
from database.models import Competitor
from database.repositories.competitor_repository import CompetitorRepository
from crawler.utils.company_name_normalizer import normalize, find_similar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def normalize_all():
    with get_session() as session:
        repo = CompetitorRepository(session)
        all_competitors = repo.list_all()
        logger.info(f"Total competitors found: {len(all_competitors)}")

        normalized_seen = {}
        merges = 0

        for comp in all_competitors:
            raw = comp.raw_names or comp.normalized_name
            norm = normalize(raw)
            if norm in normalized_seen:
                existing = normalized_seen[norm]
                logger.info(f"Merging '{comp.normalized_name}' into '{existing.normalized_name}'")
                session.delete(comp)
                merges += 1
            else:
                comp.normalized_name = norm
                normalized_seen[norm] = comp

        if merges > 0:
            session.commit()
            logger.info(f"Merged {merges} duplicate competitors")
        else:
            logger.info("No duplicates found")


if __name__ == "__main__":
    normalize_all()
