from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.dont_write_bytecode = True

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawler.config_driven_crawler import detect_charset, metadata_charset, safe_http_url
from utils.string_normalizer import normalize, normalize_records
from scripts.validate_crawler_config import require_valid_config

AGENCY_TYPE_DEFAULTS = {
    "ministry": {"delay": 10.0, "retry": 5, "timeout": 30, "max_depth": 3},
    "prefecture": {"delay": 3.0, "retry": 3, "timeout": 20, "max_depth": 3},
    "municipality": {"delay": 2.0, "retry": 3, "timeout": 20, "max_depth": 3},
    "quasi": {"delay": 5.0, "retry": 3, "timeout": 20, "max_depth": 2},
    "default": {"delay": 3.0, "retry": 3, "timeout": 15, "max_depth": 2},
}
PDF_LINK_KEYWORDS = ["入札", "公告", "仕様書", "見積", "公募", "PDF"]
PAGINATION_SELECTORS = [
    "a.next", "a[rel='next']", "li.next a", ".pagination .next a", "a#next",
    "a[title*='次']", "a[title*='next']", "a.pagination_next", ".pagnext",
    "a[aria-label='Next']", "a[aria-label='次へ']",
]
PAGE_LINK_SELECTORS = [
    "a.bid-link", "a[href*='detail']", "a[href*='view']", "a[href*='show']",
    "table.list a", "tr td a", "ul li a", "[data-url]", "[data-href]",
]


def detect_charset_from_html(html):
    return metadata_charset(html) or "utf-8"


def safe_name(name):
    value = re.sub(r'[^\w]', '_', name).strip("_").lower() or "agency"
    if len(value.encode("utf-8")) > 180:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        value = value.encode("utf-8")[:160].decode("utf-8", errors="ignore") + "_" + digest
    return value


def class_name(name):
    value = re.sub(r'[^\w]', '', name) + "Fetcher"
    return value if value.isidentifier() else "AgencyFetcher"


def generate_config_dict(name, url, agency_type="default", list_item_selector=None,
                         detail_selector=None, pagination_selectors=None,
                         pdf_keywords=None, max_pages=100, detail_fields=None, aliases=None):
    if not safe_http_url(url):
        raise ValueError("A supplied HTTP(S) URL is required")
    agency_type = {"city": "municipality", "ward": "municipality", "special_ward": "municipality",
                   "manual_ministry": "ministry", "manual_quasi": "quasi"}.get(agency_type, agency_type)
    defaults = AGENCY_TYPE_DEFAULTS.get(agency_type, AGENCY_TYPE_DEFAULTS["default"])
    if detail_fields is None:
        detail_fields = {
            "title": {"selector": "h1", "attr": "text"},
            "budget": {"selector": ".budget", "attr": "text"},
            "deadline": {"selector": ".deadline", "attr": "text"},
        }
    config = {
        "agency_name": normalize(name, aliases), "agency_type": agency_type,
        "base_url": url, "list_url": url, "start_url": url,
        "list_item_selector": list_item_selector if list_item_selector is not None else ", ".join(PAGE_LINK_SELECTORS),
        "detail_selector": detail_selector if detail_selector is not None else "div.detail",
        "pagination": {
            "next_button_selectors": PAGINATION_SELECTORS.copy() if pagination_selectors is None else pagination_selectors,
            "max_pages": max_pages,
        },
        "pdf_detection": {"extension_pattern": ".pdf", "text_keywords": PDF_LINK_KEYWORDS.copy() if pdf_keywords is None else pdf_keywords},
        "dynamic_links": {"data_url_attribute": "data-url", "data_href_attribute": "data-href"},
        "encoding": {"preferred": "utf-8", "auto_detect": True,
                     "fallback_encodings": ["utf-8", "shift_jis", "euc-jp", "cp932"]},
        "crawl_settings": {**defaults, "user_agent": "ConfigDrivenCrawler/1.0"},
        "detail_fields": detail_fields, "parser": "html", "page_format": "html",
    }
    return require_valid_config(config)


def render_config_yaml(config):
    require_valid_config(config)
    return yaml.safe_dump(config, allow_unicode=True, sort_keys=False)


def render_fetcher_py(config):
    require_valid_config(config)
    payload = repr(json.dumps(config, ensure_ascii=True, allow_nan=False))
    return (
        "import json\n"
        "from crawler.config_driven_crawler import ConfigDrivenCrawler\n\n\n"
        f"class {class_name(config['agency_name'])}(ConfigDrivenCrawler):\n"
        "    def __init__(self, **kwargs):\n"
        f"        config = json.loads({payload})\n"
        "        super().__init__(config=config, **kwargs)\n"
    )


def write_outputs(output_dir, outputs):
    output = Path(output_dir)
    seen = set()
    for filename, content in outputs:
        if Path(filename).name != filename or filename.casefold() in seen:
            raise ValueError(f"{output / filename}: output filename collision or unsafe name")
        seen.add(filename.casefold())
        path = output / filename
        if path.exists() or path.is_symlink():
            raise ValueError(f"{path}: output already exists; refusing overwrite")
    if not outputs:
        raise ValueError(f"{output}: no configurations generated")
    output.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for filename, content in outputs:
            path = output / filename
            with path.open("x", encoding="utf-8") as stream:
                created.append(path)
                stream.write(content)
    except OSError:
        for path in created:
            path.unlink()
        raise
    return [str(path) for path in created]


def generate_from_registry(output_dir="crawler/generated", registry_type="municipality", dry_run=False,
                           aliases=None, timestamp_field="updated_at", list_item_selector=None,
                           detail_selector=None, max_pages=100):
    from scripts.list_registered_agencies import REGISTRY_FACTORIES, _placeholder

    if registry_type not in REGISTRY_FACTORIES:
        raise ValueError(f"Unknown registry type: {registry_type}")
    records = normalize_records(REGISTRY_FACTORIES[registry_type]().all_records(), aliases, timestamp_field)
    outputs = []
    used = set()
    for record in records:
        url = safe_http_url(record.bid_url_pattern)
        if not record.name or not url or _placeholder(url):
            continue
        config = generate_config_dict(record.name, url, record.type or registry_type,
                                      list_item_selector, detail_selector, max_pages=max_pages)
        config["municipality_code"] = record.municipality_code
        config["parent_id"] = record.parent_id
        config["url_status"] = "unverified"
        config["registry_source"] = registry_type
        filename = safe_name(record.name)
        if filename in used:
            identity = json.dumps([record.identity, record.parent_id, record.region, record.category, url])
            digest = hashlib.sha256(identity.encode()).hexdigest()[:12]
            filename = f"{filename}_{digest}"
        stem = filename
        suffix = 2
        while filename in used:
            filename = f"{stem}_{suffix}"
            suffix += 1
        used.add(filename)
        require_valid_config(config, str(Path(output_dir) / f"{filename}_crawler.yaml"))
        outputs.append((f"{filename}_crawler.yaml", render_config_yaml(config)))
    if not outputs:
        raise ValueError(f"{registry_type}: no valid registry configurations generated")
    if dry_run:
        for _, content in outputs:
            print("---\n" + content, end="")
        return []
    return write_outputs(output_dir, outputs)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate static crawler config and fetcher")
    parser.add_argument("--name")
    parser.add_argument("--url")
    parser.add_argument("--agency-type", default="default", choices=list(AGENCY_TYPE_DEFAULTS))
    parser.add_argument("--output-dir", default="config")
    parser.add_argument("--config-only", action="store_true")
    parser.add_argument("--registry", action="store_true")
    parser.add_argument("--registry-type", default="municipality", choices=[
        "prefecture", "city", "municipality", "ministry", "quasi", "manual_ministry", "manual_quasi"])
    parser.add_argument("--list-item-selector", default=None)
    parser.add_argument("--detail-selector", default=None)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.registry:
            generate_from_registry(args.output_dir, args.registry_type, args.dry_run,
                                   list_item_selector=args.list_item_selector,
                                   detail_selector=args.detail_selector, max_pages=args.max_pages)
            return
        if not args.name or not args.url:
            parser.error("--name and --url are required when not using --registry")
        config = generate_config_dict(args.name, args.url, args.agency_type,
                                      args.list_item_selector, args.detail_selector, max_pages=args.max_pages)
        filename = safe_name(args.name)
        outputs = [(f"{filename}_crawler.yaml", render_config_yaml(config))]
        if not args.config_only:
            source = render_fetcher_py(config)
            compile(source, f"{filename}_fetcher.py", "exec")
            outputs.append((f"{filename}_fetcher.py", source))
        if args.dry_run:
            print(outputs[0][1], end="")
            return
        for path in write_outputs(args.output_dir, outputs):
            print(f"Generated: {path}")
    except (ValueError, TypeError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
