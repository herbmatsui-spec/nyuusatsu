from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml

from database.engine import engine, get_session
from database.models import create_all_quality_tables
from database.models.quality_threshold import QualityThreshold


DEFAULT_PATH = Path("config/quality_thresholds.yaml")


def seed_quality_thresholds(path: str | Path = DEFAULT_PATH) -> int:
    create_all_quality_tables(engine)
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    inserted = 0
    with get_session() as session:
        for metric_name, values in config.get("metrics", {}).items():
            if session.query(QualityThreshold).filter_by(metric_name=metric_name).first():
                continue
            warn_at = values.get("warning", values.get("warn_at"))
            alert_at = values.get("critical", values.get("alert_at"))
            if warn_at is None or alert_at is None:
                continue
            session.add(
                QualityThreshold(
                    metric_name=metric_name,
                    warn_at=float(warn_at),
                    alert_at=float(alert_at),
                )
            )
            inserted += 1
        session.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="品質しきい値のデフォルト値を登録します")
    parser.add_argument("--path", default=str(DEFAULT_PATH))
    args = parser.parse_args()
    count = seed_quality_thresholds(args.path)
    print(f"品質しきい値を登録しました ({count} 件)")


if __name__ == "__main__":
    main()
