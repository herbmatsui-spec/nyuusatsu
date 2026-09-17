"""LLM抽出フィールドの品質監視ジョブ

- LLM抽出構造化カラム（budget_amount / qualifications / delivery_deadline / deliverables）の
  欠損率・不自然値率を QualityMetricsService 経由で収集し、QualityMetric に保存する。
- しきい値評価は既存の evaluate_quality_alerts ジョブ（Daily 05:45）が QualityMetric を参照して行うため、
  本スクリプトは収集のみを担う（重複評価・二重通知を避ける）。
- 単体実行も可能: python scripts/monitor_llm_extraction_quality.py [--date-range START END]

使用例:
    python scripts/monitor_llm_extraction_quality.py
    python scripts/monitor_llm_extraction_quality.py --date-range 2026-09-01 2026-09-30
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.engine import engine, get_session
from database.models import create_all_quality_tables
from database.models.quality_metric import QualityMetric
from scripts.collect_quality_metrics import _parse_date
from services.quality_metrics_service import QualityMetricsService

logger = logging.getLogger(__name__)

LLM_METRIC_PREFIX = "llm_"


def run(date_range=None) -> dict:
    """LLM抽出フィールド品質メトリクスを収集・保存する。

    Returns:
        保存されたメトリクスの辞書。
    """
    create_all_quality_tables(engine)
    with get_session() as session:
        date_start, date_end = date_range if date_range else (None, None)
        qms = QualityMetricsService(session, date_start=date_start, date_end=date_end)
        metrics = qms.collect_llm_extraction_quality()
        if not metrics:
            logger.warning("LLM抽出品質メトリクスが空のため保存をスキップしました")
            return {}
        for name, value in metrics.items():
            session.add(QualityMetric(
                metric_name=name,
                value=value,
                period_start=date_start,
                period_end=date_end,
            ))
        session.commit()
        logger.info("LLM抽出品質メトリクスを保存しました: %d 件", len(metrics))
        print(f"LLM抽出品質メトリクスを収集・保存しました ({len(metrics)} 件)")
        return metrics


def main():
    parser = argparse.ArgumentParser(
        description="LLM抽出フィールドの品質メトリクス収集ジョブ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python scripts/monitor_llm_extraction_quality.py
  python scripts/monitor_llm_extraction_quality.py --date-range 2026-09-01 2026-09-30
        """,
    )
    parser.add_argument(
        "--date-range", nargs=2, metavar=("START", "END"),
        help="過去分を再収集する期間 (YYYY-MM-DD 形式)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    date_range = None
    if args.date_range:
        date_range = (_parse_date(args.date_range[0]), _parse_date(args.date_range[1]))
    run(date_range=date_range)


if __name__ == "__main__":
    main()
