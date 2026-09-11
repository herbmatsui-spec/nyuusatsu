"""品質メトリクス収集ジョブ

- 定期的に呼び出され、QualityMetricsService が計算したメトリクスをデータベースに保存します。
- スケジューラ (cron / APScheduler) から実行することを想定しています。
- --date-range START END で過去分再収集可能。

使用例:
    python scripts/collect_quality_metrics.py
    python scripts/collect_quality_metrics.py --date-range 2024-01-01 2024-01-31
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.engine import get_session, engine
from database.models import create_all_quality_tables
from services.quality_metrics_service import QualityMetricsService
from database.models.quality_metric import QualityMetric
from scripts.seed_quality_thresholds import seed_quality_thresholds

logger = logging.getLogger(__name__)


def _parse_date(s: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {s}")


def run(date_range=None):
    """品質メトリクスを収集・保存する。
    date_range に (start, end) の datetime タプルを渡すとその期間のデータで計算する。
    """
    create_all_quality_tables(engine)
    seed_quality_thresholds()

    with get_session() as session:
        date_start, date_end = date_range if date_range else (None, None)
        qms = QualityMetricsService(session, date_start=date_start, date_end=date_end)

        metrics = qms.collect_all_metrics()
        for name, value in metrics.items():
            metric = QualityMetric(metric_name=name, value=value)
            session.add(metric)

        session.commit()
        logger.info("品質メトリクスを収集・保存しました: %d 件", len(metrics))
        print(f"品質メトリクスを収集・保存しました ({len(metrics)} 件)")


def main():
    parser = argparse.ArgumentParser(
        description="品質メトリクスを収集・保存するジョブ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python scripts/collect_quality_metrics.py
  python scripts/collect_quality_metrics.py --date-range 2024-01-01 2024-01-31
        """,
    )
    parser.add_argument(
        "--date-range",
        nargs=2,
        metavar=("START", "END"),
        help="過去分再収集する期間 (YYYY-MM-DD 形式)",
    )
    args = parser.parse_args()

    date_range = None
    if args.date_range:
        date_range = (_parse_date(args.date_range[0]), _parse_date(args.date_range[1]))

    run(date_range=date_range)


if __name__ == "__main__":
    main()
