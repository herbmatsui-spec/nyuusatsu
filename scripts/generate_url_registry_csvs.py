"""URLレジストリCSV生成スクリプト。

``data/master/municipality_codes.csv`` から都道府県・主要市区町村の
base_url / bid_url_pattern（GEPS検索URL）を取り出し、それぞれ
``data/prefecture_urls.csv`` と ``data/city_urls.csv`` を生成する。

実行:
    python scripts/generate_url_registry_csvs.py
"""
from __future__ import annotations

import csv
import os
import sys
import urllib.parse
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
MASTER_PATH = DATA_DIR / "master" / "municipality_codes.csv"

PREFECTURE_CSV = DATA_DIR / "prefecture_urls.csv"
CITY_CSV = DATA_DIR / "city_urls.csv"

PREFECTURE_HEADER = ["municipality_code", "name", "base_url", "bid_url_pattern", "bid_system", "parser_type"]
CITY_HEADER = ["municipality_code", "prefecture", "name", "type", "base_url", "bid_url_pattern", "bid_system", "parser_type"]

CITY_CATEGORIES = ("designated_city", "core_city", "special_ward")


def geps_url(municipality_code: str, name: str) -> str:
    pref = str(municipality_code).zfill(2)[:2]
    return f"https://search.geps.go.jp/search?q={urllib.parse.quote(name)}&pref={pref}"


def load_master() -> List[dict]:
    with open(MASTER_PATH, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def build_prefecture_rows(rows: List[dict]) -> List[Tuple]:
    out = []
    for r in rows:
        if r["category"].strip() != "prefecture":
            continue
        mcode = r["municipality_code"].strip()
        name = r["name"].strip()
        base_url = (r.get("base_url") or "").strip()
        out.append((mcode, name, base_url, geps_url(mcode, name), "GEPS", "prefecture"))
    return out


def build_city_rows(rows: List[dict]) -> List[Tuple]:
    out = []
    for r in rows:
        cat = r["category"].strip()
        if cat not in CITY_CATEGORIES:
            continue
        mcode = r["municipality_code"].strip()
        name = r["name"].strip()
        region = r["region"].strip()
        base_url = (r.get("base_url") or "").strip()
        out.append((mcode, region, name, cat, base_url, geps_url(mcode, name), "GEPS", "generic"))
    return out


def write_csv(path: Path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")


def main():
    if not MASTER_PATH.exists():
        print(f"Error: master CSV not found at {MASTER_PATH}", file=sys.stderr)
        sys.exit(1)
    rows = load_master()
    pref_rows = build_prefecture_rows(rows)
    city_rows = build_city_rows(rows)
    write_csv(PREFECTURE_CSV, PREFECTURE_HEADER, pref_rows)
    write_csv(CITY_CSV, CITY_HEADER, city_rows)


if __name__ == "__main__":
    main()
