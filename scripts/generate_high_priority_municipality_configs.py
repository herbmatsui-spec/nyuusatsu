"""Generate crawler config JSON files for high-priority municipalities.

Reads ``data/high_priority_municipalities.csv`` and produces one JSON config
file per municipality under
``crawler/parsers/agency_config/municipalities/high_priority/``.

Each file follows the same format as ``ehime.json``: a dict keyed by the
municipality name, with config fields populated from the template and the
CSV data.
"""

import csv
import json
import os
import sys
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "high_priority_municipalities.csv")
TEMPLATE_PATH = os.path.join(BASE_DIR, "crawler", "parsers", "agency_config", "municipality_template.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "crawler", "parsers", "agency_config", "municipalities", "high_priority")


def sanitize_filename(name):
    """Make a municipality name safe for use in a filename."""
    safe = name
    for ch in ("/", "\\", ":", "*", "?", '"', "<", ">", "|", " "):
        safe = safe.replace(ch, "_")
    return safe


def derive_url_includes(entry_url):
    """Extract path components from entry_url for url_includes.

    If the URL has a path beyond the root, include it.
    Otherwise default to ["/"] (search from top).
    """
    parsed = urlparse(entry_url)
    path = parsed.path
    if path and path != "/":
        # Use the path prefix up to the last segment
        parts = path.rstrip("/").split("/")
        if len(parts) > 1 and parts[-1]:
            return ["/" + parts[0] + "/"]
        return [path]
    return ["/"]


def load_template():
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV not found at {CSV_PATH}")
        sys.exit(1)

    if not os.path.exists(TEMPLATE_PATH):
        print(f"Error: Template not found at {TEMPLATE_PATH}")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    template = load_template()
    print(f"Loaded template from {TEMPLATE_PATH}")

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} high-priority municipalities from {CSV_PATH}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    generated = 0
    errors = 0

    for i, row in enumerate(rows, 1):
        muni_code = row.get("municipality_code", "").strip()
        name = row.get("name", "").strip()
        population = row.get("population", "").strip()
        base_url = row.get("base_url", "").strip()

        if not name or not base_url:
            print(f"  [{i}/{len(rows)}] SKIP: missing name or URL for {muni_code}")
            errors += 1
            continue

        config = dict(template)
        config["municipality_code"] = muni_code
        config["name"] = name
        config["entry_url"] = base_url
        config["url_includes"] = derive_url_includes(base_url)

        config_data = {name: config}

        safe_name = sanitize_filename(name)
        filename = f"{muni_code}_{safe_name}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            print(f"  [{i}/{len(rows)}] OK: {filename}")
            generated += 1
        except Exception as e:
            print(f"  [{i}/{len(rows)}] ERROR: {name} -> {e}")
            errors += 1

    print()
    print(f"=== Summary ===")
    print(f"  Generated: {generated} config files")
    print(f"  Errors: {errors}")
    print(f"  Total processed: {len(rows)}")

    if errors > 0:
        print(f"\nWARNING: {errors} errors occurred during generation")
        sys.exit(1)

    print(f"\nSuccessfully generated {generated} municipality config files in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
