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
from utils.string_normalizer import normalize_records
from crawler.registry.prefecture_registry import PrefectureRegistry
from crawler.registry.city_registry import CityRegistry
from crawler.registry.municipality_registry import MunicipalityRegistry
from crawler.registry.url_validator import UrlValidator, validate_url
from crawler.registry.ministry_registry import MinistryRegistry
from crawler.registry.quasi_agency_registry import QuasiAgencyRegistry
from crawler.registry.manual_ministry_registry import ManualMinistryRegistry
from crawler.registry.manual_quasi_registry import ManualQuasiRegistry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sync_registry_to_db")

REGISTRY_FACTORIES = {
    "prefecture": PrefectureRegistry,
    "city": CityRegistry,
    "municipality": MunicipalityRegistry,
    "manual_ministry": ManualMinistryRegistry,
    "manual_quasi": ManualQuasiRegistry,
    "ministry": MinistryRegistry,
    "quasi": QuasiAgencyRegistry,
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
    "quasi": "外郭団体",
    "manual_ministry": "国",
    "manual_quasi": "外郭団体",
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
    category = (category or "").strip()
    jp_name = CATEGORY_NAME_MAP.get(category, category)
    category_id = cat_map.get(jp_name)
    if category_id is None:
        raise ValueError(f"Unknown or unseeded category: {category!r}")
    return category_id


def find_agency(session, record: RegistryRecord, category_id: Optional[int]):
    code = (record.municipality_code or "").strip()
    if code:
        agency = session.query(Agency).filter(Agency.municipality_code == code).one_or_none()
        if agency is not None and agency.category_id not in (None, category_id):
            raise ValueError(f"Category conflict for municipality code: {code}")
        return agency
    agency = session.query(Agency).filter(
        Agency.name == record.name, Agency.category_id == category_id,
        (Agency.municipality_code.is_(None)) | (Agency.municipality_code == ""),
    ).one_or_none()
    if agency is None:
        agency = session.query(Agency).filter(
            Agency.name == record.name,
            Agency.category_id.is_(None),
            (Agency.municipality_code.is_(None)) | (Agency.municipality_code == ""),
        ).one_or_none()
    return agency


def find_url_registry(session, record: RegistryRecord, category_id: Optional[int]):
    query = session.query(UrlRegistry)
    code = (record.municipality_code or "").strip()
    if code:
        existing = query.filter(UrlRegistry.municipality_code == code).one_or_none()
        if existing is not None and existing.category_id not in (None, category_id):
            raise ValueError(f"Category conflict for municipality code: {code}")
        return existing
    query = query.filter(
        (UrlRegistry.municipality_code == "") | UrlRegistry.municipality_code.is_(None),
        UrlRegistry.agency_name == record.name,
    )
    existing = query.filter(UrlRegistry.category_id == category_id).one_or_none()
    if existing is None:
        existing = query.filter(UrlRegistry.category_id.is_(None)).one_or_none()
    return existing


def upsert_agency(
    session,
    record: RegistryRecord,
    cat_map: Dict[str, int],
    only_unset: bool,
) -> str:
    """agencies テーブルへ UPSERT。base_url と bid_url_pattern を更新する。"""
    category_id = resolve_category_id(session, cat_map, record.category)
    now = datetime.utcnow()

    if not record.name.strip():
        raise ValueError("Agency name must not be empty")
    agency = find_agency(session, record, category_id)
    if (agency is not None and not record.municipality_code and agency.region
            and record.region and agency.region != record.region):
        raise ValueError(f"Conflicting regions for codeless agency: {record.name!r}")

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
            bid_url_pattern=record.bid_url_pattern,
            created_at=now,
            updated_at=now,
        )
        session.add(agency)
        session.flush()
        return f"created {agency.id}"

    changed = False
    if record.base_url and (not only_unset or not agency.base_url) and (agency.base_url or "") != record.base_url:
        agency.base_url = record.base_url
        changed = True
    if record.name and (agency.name or "") != record.name:
        agency.name = record.name
        changed = True
    if record.region and (agency.region or "") != record.region:
        agency.region = record.region
        changed = True
    if record.bid_url_pattern:
        if not only_unset or not (agency.bid_url_pattern or ""):
            if (agency.bid_url_pattern or "") != record.bid_url_pattern:
                agency.bid_url_pattern = record.bid_url_pattern
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
    existing = find_url_registry(session, record, category_id)

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
    if existing.agency_name != record.name:
        existing.agency_name = record.name
        updated = True
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


def resolve_parent(session, model, reference: str):
    name_column = model.name if model is Agency else model.agency_name
    if reference.startswith("code:"):
        query = session.query(model).filter(model.municipality_code == reference[5:])
    elif reference.startswith("name:"):
        query = session.query(model).filter(name_column == reference[5:])
    else:
        query = session.query(model).filter(
            (model.municipality_code == reference) | (name_column == reference)
        )
    matches = query.all()
    if len(matches) != 1:
        reason = "Missing" if not matches else "Ambiguous"
        raise ValueError(f"{reason} parent {reference!r} in {model.__tablename__}")
    return matches[0]


def validate_parent_graph(session, model, proposed: Dict[int, int]) -> None:
    parents = {row.id: row.parent_id for row in session.query(model).all()}
    parents.update(proposed)
    visited = set()
    for start in parents:
        path = set()
        current = start
        while current is not None and current not in visited:
            if current in path:
                raise ValueError(f"Cyclic parent in {model.__tablename__}: {current}")
            if current not in parents:
                raise ValueError(f"Missing parent in {model.__tablename__}: {current}")
            path.add(current)
            current = parents[current]
        visited.update(path)


def preprocess_records(records, aliases=None, timestamp_field="updated_at"):
    records = normalize_records(records, aliases, timestamp_field)
    scopes = {}
    for record in records:
        if record.municipality_code:
            continue
        key = (record.name, CATEGORY_NAME_MAP.get(record.category, record.category))
        scope = (record.region, record.parent_id)
        if key in scopes and scopes[key] != scope:
            raise ValueError(f"Conflicting parents or regions for codeless agency: {record.name!r}")
        scopes[key] = scope
    return records


def sync_records(session, records: List[RegistryRecord], only_unset: bool = False, aliases=None):
    records = preprocess_records(records, aliases)
    results = []
    with session.begin_nested():
        cat_map = load_category_map(session)
        rows = []
        for record in records:
            action = upsert_agency(session, record, cat_map, only_unset)
            raction = upsert_url_registry(session, record, cat_map)
            category_id = resolve_category_id(session, cat_map, record.category)
            rows.append((record, find_agency(session, record, category_id),
                         find_url_registry(session, record, category_id)))
            results.append((action, raction))

        agency_parents: Dict[int, int] = {}
        registry_parents: Dict[int, int] = {}
        for record, agency, registry in rows:
            if not record.parent_id:
                continue
            parent_agency = resolve_parent(session, Agency, record.parent_id)
            parent_registry = resolve_parent(session, UrlRegistry, record.parent_id)
            if not record.municipality_code:
                for child, parent in ((agency, parent_agency), (registry, parent_registry)):
                    if child.parent_id is not None and child.parent_id != parent.id:
                        raise ValueError(f"Conflicting parents for codeless agency: {record.name!r}")
            for proposed, child, parent in (
                (agency_parents, agency, parent_agency),
                (registry_parents, registry, parent_registry),
            ):
                if child.id in proposed and proposed[child.id] != parent.id:
                    raise ValueError(f"Conflicting parents for {record.identity}")
                proposed[child.id] = parent.id

        validate_parent_graph(session, Agency, agency_parents)
        validate_parent_graph(session, UrlRegistry, registry_parents)
        for record, agency, registry in rows:
            if agency.id in agency_parents:
                agency.parent_id = agency_parents[agency.id]
            if registry.id in registry_parents:
                registry.parent_id = registry_parents[registry.id]
        session.flush()
    return results


def collect_records(registry_type: str, registry_path: Optional[str] = None) -> List[RegistryRecord]:
    if registry_type == "all":
        records: List[RegistryRecord] = []
        for rtype in ("prefecture", "city", "municipality", "ministry", "quasi", "manual_ministry", "manual_quasi"):
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
    parser.add_argument("--type", choices=["prefecture", "city", "municipality", "ministry", "quasi", "manual_ministry", "manual_quasi", "all"], default="prefecture")
    parser.add_argument("--registry-path", help="Override CSV path for the registry.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to the DB.")
    parser.add_argument("--only-unset", action="store_true", help="Only update agencies whose base_url is empty.")
    parser.add_argument("--validate", action="store_true", help="Validate URLs via HEAD/GET before syncing.")
    args = parser.parse_args()

    records = preprocess_records(collect_records(args.type, args.registry_path))
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

    accepted = []
    for rec in records:
        if validator is not None and rec.base_url:
            res = validator.validate(rec.base_url)
            if not res.is_valid:
                logger.warning("Skipping invalid URL %s (%s): %s", rec.name, rec.base_url, res.error)
                invalid += 1
                continue
        accepted.append(rec)

    with get_session() as session:
        try:
            results = sync_records(session, accepted, args.only_unset)
            synced = list(zip(accepted, results))
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Registry sync rejected; no registry changes committed")
            raise
        for rec, (action, raction) in synced:
            if action.startswith("created") and raction.startswith("created"):
                created += 1
            else:
                updated += 1
            logger.info("SYNCED %s (%s): agency[%s] registry[%s]",
                        rec.name, rec.municipality_code, action, raction)
        logger.info("Sync complete: created=%d updated=%d skipped=%d invalid=%d",
                    created, updated, skipped, invalid)


if __name__ == "__main__":
    main()
