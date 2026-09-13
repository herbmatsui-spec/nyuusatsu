"""Seeders for reference/master data.

Reconstructed best-effort: the original CSV-backed implementations are not
available, so these read an optional CSV when present and otherwise no-op.
"""
import csv
import os
from typing import List, Optional

DEFAULT_MASTER_CSV = os.path.join(os.path.dirname(__file__), "qualification_tags.csv")


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
        code = r.get("tag_code") or r.get("code") or r.get("id")
        if not code:
            continue
        existing = session.query(QualificationTag).filter_by(tag_code=code).first()
        if existing:
            continue
        # Map CSV columns to model fields
        tag_data = {}
        if "tag_code" in r:
            tag_data["tag_code"] = r["tag_code"]
        elif "code" in r:
            tag_data["tag_code"] = r["code"]
        if "display_name" in r:
            tag_data["display_name"] = r["display_name"]
        elif "name" in r:
            tag_data["display_name"] = r["name"]
        if "category" in r:
            tag_data["category"] = r["category"]
        if "description" in r:
            tag_data["description"] = r["description"]
        if "grade_required" in r:
            tag_data["grade_required"] = r["grade_required"]
        if "region_required" in r:
            tag_data["region_required"] = r["region_required"]
        if "is_unified_qualification" in r:
            val = r["is_unified_qualification"]
            tag_data["is_unified_qualification"] = val in ("1", "true", "True", "yes", "yes")
        if "compatible_grades" in r:
            tag_data["compatible_grades"] = r["compatible_grades"]
        tag = QualificationTag(**tag_data)
        session.add(tag)
        inserted += 1
    session.commit()
    return {"inserted": inserted, "total": len(rows)}
