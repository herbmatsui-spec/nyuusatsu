"""
Bid一覧CSVエクスポート

Usage:
    py -3 scripts/export_bids_csv.py
    py -3 scripts/export_bids_csv.py --output data/bids_export.csv
"""
import sys
import os
import csv
import io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import argparse
from database.session import get_db
from database.models import Bid

def main():
    parser = argparse.ArgumentParser(description="Bid一覧CSVエクスポート")
    parser.add_argument("--output", type=str, default="data/bids_export.csv")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with get_db() as session:
        bids = session.query(Bid).order_by(Bid.id).all()
        print(f"エクスポート対象: {len(bids)}件")

        with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "filename", "source_url", "organization_name",
                "budget", "deadline", "qualifications", "deliverables",
                "industry_category", "current_status", "created_at"
            ])
            for b in bids:
                writer.writerow([
                    b.id, b.filename, b.source_url or "",
                    b.organization_name or "", b.budget or "",
                    b.deadline or "", b.qualifications or "",
                    b.deliverables or "", b.industry_category or "",
                    b.current_status or "", b.created_at or ""
                ])

    print(f"CSVエクスポート完了: {args.output}")

if __name__ == "__main__":
    main()
