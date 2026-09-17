from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawler.registry import RegistryRecord
from crawler.registry.prefecture_registry import PrefectureRegistry
from crawler.registry.city_registry import CityRegistry
from crawler.registry.municipality_registry import MunicipalityRegistry
from crawler.registry.ministry_registry import MinistryRegistry
from crawler.registry.quasi_agency_registry import QuasiAgencyRegistry
from crawler.registry.manual_ministry_registry import ManualMinistryRegistry
from crawler.registry.manual_quasi_registry import ManualQuasiRegistry

logger = logging.getLogger(__name__)

REGISTRY_FACTORIES = {
    "prefecture": PrefectureRegistry,
    "city": CityRegistry,
    "municipality": MunicipalityRegistry,
    "ministry": MinistryRegistry,
    "quasi": QuasiAgencyRegistry,
    "manual_ministry": ManualMinistryRegistry,
    "manual_quasi": ManualQuasiRegistry,
}
TARGETS = {
    "prefecture": 47, "city": 0, "municipality": 1800,
    "ministry": 2000, "quasi": 500,
    "manual_ministry": 0, "manual_quasi": 0,
}
CATEGORY_ALIASES = {
    "city": "municipality", "manual_ministry": "ministry",
    "manual_quasi": "quasi",
}
MISSING_TYPE_BY_CATEGORY = {
    "prefecture": ["支庁", "振興局", "土木事務所"],
    "municipality": ["市", "町", "村", "区"],
    "ministry": ["地方整備局", "地方防衛局", "地方農政局", "森林管理局", "出張所"],
    "quasi": ["独立行政法人", "地方独立行政法人", "公社", "土地改良区", "水道企業団", "広域連合", "一部事務組合"],
}


def _load_records(registry_type: str) -> list[RegistryRecord]:
    factory = REGISTRY_FACTORIES.get(registry_type)
    return factory().all_records() if factory else []


def _group_by_subcategory(records: list[RegistryRecord]) -> dict[str, list[str]]:
    groups = defaultdict(list)
    suffixes = ["出張所", "事務所", "支庁", "庁", "課", "部", "局", "署", "区", "市", "町", "村"]
    for rec in records:
        suffix = next((s for s in suffixes if rec.name.endswith(s)), "その他")
        groups[suffix].append(rec.name)
    return dict(groups)


def analyze_missing_types(records: list[RegistryRecord], registry_type: str) -> list[str]:
    category = CATEGORY_ALIASES.get(registry_type, registry_type)
    missing = []
    for kind in MISSING_TYPE_BY_CATEGORY.get(category, []):
        if category == "municipality":
            present = any(r.name.endswith(kind) for r in records)
        else:
            present = any(kind in r.name for r in records)
        if not present:
            missing.append(kind)
    return missing


def _safe_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        return bool(parts.scheme in ("http", "https") and parts.hostname
                    and not parts.username and not parts.password)
    except ValueError:
        return False


def _placeholder(url: str) -> bool:
    return bool(url and (urlsplit(url).hostname == "search.geps.go.jp"
                        or "{" in url or "}" in url))


def _unique_groups(records):
    codes_by_name = defaultdict(set)
    for rec in records:
        if rec.municipality_code.strip():
            codes_by_name[(rec.name.strip(), rec.parent_id)].add(rec.identity)
    groups = defaultdict(list)
    for rec in records:
        if not rec.name.strip() and not rec.municipality_code.strip():
            continue
        identity = rec.identity
        aliases = codes_by_name[(rec.name.strip(), rec.parent_id)]
        if not rec.municipality_code.strip() and len(aliases) == 1:
            identity = next(iter(aliases))
        key = (identity, rec.parent_id if identity.startswith("name:") else "")
        groups[key].append(rec)
    return list(groups.values())


def _report(records, category, target):
    groups = _unique_groups(records)
    unique = [group[0] for group in groups]
    coverage = defaultdict(int)
    for group in groups:
        urls = [r.bid_url_pattern for r in group if _safe_url(r.bid_url_pattern)]
        candidates = [u for u in urls if not _placeholder(u)]
        verified = any(
            r.extra.get("verified_bid_url") in candidates
            and r.extra.get("verified_at")
            and r.extra.get("url_status") == "reachable"
            for r in group
        )
        state = ("reachable_verified" if verified else "unverified_url"
                 if candidates else "placeholder_only" if urls else "missing_url")
        coverage[state] += 1
    count = len(groups)
    return {
        "count": count, "raw_count": len(records), "target": target,
        "target_is_approximate": True, "shortfall": max(target - count, 0),
        "missing_types": analyze_missing_types(unique, category),
        "missing_types_basis": "name-based candidates for review, not confirmed absence",
        "categories": _group_by_subcategory(unique),
        "sample_names": [r.name for r in unique[:5]],
        "coverage": {key: coverage[key] for key in (
            "reachable_verified", "unverified_url", "placeholder_only", "missing_url")},
    }


def summarize() -> dict[str, dict]:
    summary = {}
    by_category = defaultdict(list)
    all_records = []
    sources = {}
    for rtype in REGISTRY_FACTORIES:
        records = _load_records(rtype)
        category = CATEGORY_ALIASES.get(rtype, rtype)
        all_records.extend(records)
        for rec in records:
            sources[id(rec)] = category
        summary[rtype] = _report(records, category, TARGETS[rtype])
    for group in _unique_groups(all_records):
        categories_found = {sources[id(rec)] for rec in group}
        category = next((key for key in ("prefecture", "ministry", "quasi")
                         if key in categories_found), "municipality")
        if any(rec.category == "prefecture" for rec in group):
            category = "prefecture"
        by_category[category].extend(group)
    for category in ("prefecture", "municipality", "ministry", "quasi"):
        by_category.setdefault(category, [])
    categories = {
        category: _report(records, category, TARGETS[category])
        for category, records in by_category.items()
    }
    total_count = sum(item["count"] for item in categories.values())
    total_target = sum(TARGETS.values())
    summary["_categories"] = categories
    summary["_totals"] = {
        "count": total_count,
        "raw_count": sum(item["raw_count"] for item in categories.values()),
        "target": total_target, "target_is_approximate": True,
        "shortfall": sum(item["shortfall"] for item in categories.values()),
        "coverage": {key: sum(item["coverage"][key] for item in categories.values())
                     for key in ("reachable_verified", "unverified_url", "placeholder_only", "missing_url")},
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory unique agencies; URL presence is not reachable coverage.")
    parser.add_argument("--type", choices=list(REGISTRY_FACTORIES) + ["all"], default="all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    summary = summarize()
    result = summary if args.type == "all" else summary[args.type]
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        items = summary["_categories"] if args.type == "all" else {args.type: result}
        for category, data in items.items():
            print(f"{category}: {data['count']} unique / approximate target {data['target']} / shortfall {data['shortfall']}")
            print(f"  Missing type candidates: {data['missing_types']}")
            print(f"  URL coverage (not live checked): {data['coverage']}")
        if args.type == "all":
            print(f"Totals: {summary['_totals']}")


if __name__ == "__main__":
    main()
