"""Seeders for reference/master data.

Reconstructed best-effort: the original CSV-backed implementations are not
available, so these read an optional CSV when present and otherwise no-op.
"""
import csv
import os
from typing import List, Optional

DEFAULT_MASTER_CSV = os.path.join(os.path.dirname(__file__), "..", "config", "qualification_tags.csv")


def load_master_csv(path: Optional[str] = None) -> List[dict]:
    """Load qualification-tag master rows from a CSV.

    Expected columns: code, name, category, ... (best-effort). Returns [] when
    the file is missing.
    """
    csv_path = path or DEFAULT_MASTER_CSV
    if not csv_path or not os.path.exists(csv_path):
        return []
    rows: List[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(dict(r))
    return rows


def seed_qualification_tags(session) -> dict:
    """Insert qualification tags from the master CSV (idempotent).

    Returns a stats dict ``{"inserted": int, "total": int}``.
    """
    from ..models import QualificationTag

    rows = load_master_csv()
    inserted = 0
    for r in rows:
        code = r.get("code") or r.get("id")
        if not code:
            continue
        existing = session.query(QualificationTag).filter_by(code=code).first()
        if existing:
            continue
        tag = QualificationTag(**{k: v for k, v in r.items() if hasattr(QualificationTag, k)})
        session.add(tag)
        inserted += 1
    session.commit()
    return {"inserted": inserted, "total": len(rows)}
