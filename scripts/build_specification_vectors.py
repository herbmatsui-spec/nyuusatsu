"""
Build Specification Text Vectors (TF-IDF)

Initializes the TF-IDF vector cache for specification text similarity search.
Run this script after new bids have been added with specification_text_clean populated.

Usage:
    python scripts/build_specification_vectors.py
    python scripts/build_specification_vectors.py --months 12
    python scripts/build_specification_vectors.py --output /custom/path/vectors.pkl
"""
import os
import sys
import logging
import argparse
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description="Build TF-IDF vectors for specification similarity search")
    parser.add_argument("--months", type=int, default=None, help="Time window in months (default: config value)")
    parser.add_argument("--max-docs", type=int, default=None, help="Maximum number of bids to vectorize")
    parser.add_argument("--output", type=str, default=None, help="Output pickle file path")
    parser.add_argument("--limit", type=int, default=None, help="Alias for --max-docs")
    args = parser.parse_args()

    from database.engine import get_session
    from services.text_similarity_service import TextSimilarityService

    max_docs = args.max_docs or args.limit

    with get_session() as session:
        svc = TextSimilarityService(session)
        count = svc.build(months=args.months, max_docs=max_docs)
        if count == 0:
            logger.warning("No bids with specification_text found. Nothing to build.")
            return 1

        output_path = args.output or os.path.join(svc.cache_dir, "tfidf_vectors.pkl")
        svc.save_vectors(output_path)
        logger.info("Built vectors for %d bids. Saved to %s", count, output_path)
        return 0


if __name__ == "__main__":
    sys.exit(main())
