"""レジストリ -> DB 同期スクリプト。

``crawler/registry/`` が提供するレジストリから読み込んだ URL 情報を
``agencies`` テーブルの ``base_url`` と ``url_registry`` テーブルの
``base_url`` / ``search_url`` (bid URL pattern) へ UPSERT する。

使用例:
    python scripts/sync_registry_to_db.py --type prefecture
    python scripts/sync_registry_to_db.py --type city --only-unset
    python scripts/sync_registry_to_db.py --type all --dry-run
    python scripts/sync_registry_to_db.py --type prefecture --validate
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.engine import get_session
from database.models import Agency, UrlRegistry, AgencyCategory

from crawler.registry import RegistryRecord
from crawler.registry.prefecture_registry import PrefectureRegistry
from crawler.registry.city_registry import CityRegistry
from crawler.registry.municipality_registry import MunicipalityRegistry
from crawler.registry.url_validator import UrlValidator, validate_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sync_registry_to_db")

REGISTRY_FACTORIES = {
    "prefecture": PrefectureRegistry,
    "city": CityRegistry,
    "municipality": MunicipalityRegistry,
}

CATEGORY_NAME_MAP: Dict[str, str] = {
    "prefecture": "都道府県",
    "city": "市区町村",
    "designated_city": "市区町村",
    "core_city": "市区町村",
    "special_ward": "市区町村",
    "town": "市区町村",
    "village": "市区町村",
    "municipality": "市区町村",
    "ministry": "国",
    "outer": "外郭団体",
}

SYSTEM_TYPE_DEFAULT: Dict[str, str] = {
    "prefecture": "自治体共通",
    "city": "自治体独自",
    "designated_city": "自治体独自",
    "core_city": "自治体独自",
    "special_ward": "自治体独自",
    "town": "自治体独自",
    "village": "自治体独自",
    "municipality": "自治体独自",
}


def load_category_map(session) -> Dict[str, int]:
    """category name -> id の対応表をキャッシュする。"""
    result: Dict[str, int] = {}
    for cat in session.query(AgencyCategory).all():
        result[cat.name] = cat.id
    return result


def resolve_category_id(session, cat_map: Dict[str, int], category: str) -> Optional[int]:
    if not category:
        return None
    jp_name = CATEGORY_NAME_MAP.get(category)
    if jp_name is None:
        return None
    return cat_map.get(jp_name)


def upsert_agency(
    session,
    record: RegistryRecord,
    cat_map: Dict[str, int],
    only_unset: bool,
) -> str:
    """agencies テーブルへ UPSERT。base_url を更新する。"""
    category_id = resolve_category_id(session, cat_map, record.category)
    now = datetime.utcnow()

    agency = session.query(Agency).filter(Agency.municipality_code == record.municipality_code).first()

    if agency is None:
        agency = Agency(
            name=record.name,
            type=record.type or record.category,
            region=record.region,
            base_url=record.base_url,
            municipality_code=record.municipality_code or None,
            category_id=category_id,
            priority_level=5,
            system_type=SYSTEM_TYPE_DEFAULT.get(record.category) if record.category else None,
            created_at=now,
            updated_at=now,
        )
        session.add(agency)
        session.flush()
        return f"created {agency.id}"

    if only_unset and (agency.base_url or ""):
        return "skipped(base_url already set)"

    changed = False
    if record.base_url and (agency.base_url or "") != record.base_url:
        agency.base_url = record.base_url
        changed = True
    if record.name and (agency.name or "") != record.name:
        agency.name = record.name
        changed = True
    if record.region and (agency.region or "") != record.region:
        agency.region = record.region
        changed = True
    if category_id and (agency.category_id or 0) == 0:
        agency.category_id = category_id
        changed = True
    if not agency.system_type:
        st = record.bid_system or SYSTEM_TYPE_DEFAULT.get(record.category)
        if st:
            agency.system_type = st
            changed = True
    agency.updated_at = now
    session.flush()
    return "updated" if changed else "unchanged"


def upsert_url_registry(session, record: RegistryRecord, cat_map: Dict[str, int]) -> str:
    """url_registry テーブルへ UPSERT。search_url に bid_url_pattern を格納。"""
    category_id = resolve_category_id(session, cat_map, record.category)
    existing = (
        session.query(UrlRegistry)
        .filter(UrlRegistry.municipality_code == record.municipality_code)
        .filter(UrlRegistry.agency_name == record.name)
        .first()
    )

    if record.bid_url_pattern:
        search_url = record.bid_url_pattern
    elif record.base_url:
        search_url = record.base_url
    else:
        search_url = None

    if existing is None:
        reg = UrlRegistry(
            municipality_code=record.municipality_code,
            agency_name=record.name,
            base_url=record.base_url,
            search_url=search_url,
            category_id=category_id,
            parser_type=record.parser_type or "generic",
            max_depth=2,
        )
        session.add(reg)
        session.flush()
        return "created"

    updated = False
    if record.base_url and existing.base_url != record.base_url:
        existing.base_url = record.base_url
        updated = True
    if search_url and (existing.search_url or "") != search_url:
        existing.search_url = search_url
        updated = True
    if category_id and (existing.category_id or 0) == 0:
        existing.category_id = category_id
        updated = True
    if (existing.parser_type or "") != (record.parser_type or "generic"):
        existing.parser_type = record.parser_type or "generic"
        updated = True
    session.flush()
    return "updated" if updated else "unchanged"


def collect_records(registry_type: str, registry_path: Optional[str] = None) -> List[RegistryRecord]:
    if registry_type == "all":
        records: List[RegistryRecord] = []
        for rtype in ("prefecture", "city", "municipality"):
            records.extend(collect_records(rtype, registry_path))
        return records
    factory = REGISTRY_FACTORIES.get(registry_type)
    if factory is None:
        raise ValueError(f"Unknown registry type: {registry_type}")
    if registry_path:
        registry = factory(csv_path=registry_path)
    else:
        registry = factory()
    return registry.all_records()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync URL registry CSVs into the agencies / url_registry DB tables.")
    parser.add_argument("--type", choices=["prefecture", "city", "municipality", "all"], default="prefecture")
    parser.add_argument("--registry-path", help="Override CSV path for the registry.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to the DB.")
    parser.add_argument("--only-unset", action="store_true", help="Only update agencies whose base_url is empty.")
    parser.add_argument("--validate", action="store_true", help="Validate URLs via HEAD/GET before syncing.")
    args = parser.parse_args()

    records = collect_records(args.type, args.registry_path)
    logger.info("Loaded %d records from registry '%s'.", len(records), args.type)

    validator = UrlValidator() if args.validate else None

    created = updated = skipped = 0
    invalid = 0

    if args.dry_run:
        logger.info("DRY-RUN mode: no DB writes will occur.")
        for rec in records:
            valid_label = ""
            if validator is not None and rec.base_url:
                res = validator.validate(rec.base_url)
                valid_label = f" valid={res.is_valid}"
            print(f"  {rec.municipality_code} {rec.name} base={rec.base_url} bid={rec.bid_url_pattern}{valid_label}")
        print(f"\nDry-run summary: {len(records)} records (no changes written, invalid={invalid}).")
        return

    with get_session() as session:
        cat_map = load_category_map(session)
        for rec in records:
            if validator is not None and rec.base_url:
                res = validator.validate(rec.base_url)
                if not res.is_valid:
                    logger.warning("Skipping invalid URL %s (%s): %s", rec.name, rec.base_url, res.error)
                    invalid += 1
                    continue
            try:
                action = upsert_agency(session, rec, cat_map, args.only_unset)
                raction = upsert_url_registry(session, rec, cat_map)
                if action.startswith("created") and raction.startswith("created"):
                    created += 1
                    logger.info("CREATED %s (%s) -> %s", rec.name, rec.municipality_code, rec.base_url)
                elif action.startswith("skipped"):
                    skipped += 1
                    logger.info("SKIPPED %s (%s): %s", rec.name, rec.municipality_code, action)
                else:
                    updated += 1
                    logger.info("SYNCED %s (%s): agency[%s] registry[%s]",
                                rec.name, rec.municipality_code, action, raction)
            except Exception as e:
                logger.error("Failed to sync %s: %s", rec.name, e)
                session.rollback()
                continue
        session.commit()
        logger.info("Sync complete: created=%d updated=%d skipped=%d invalid=%d",
                    created, updated, skipped, invalid)


if __name__ == "__main__":
    main()
