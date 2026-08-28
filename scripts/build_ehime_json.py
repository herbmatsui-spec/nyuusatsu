import csv, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

TSV_PATH = "docs/plans/url_probe_results/_url_includes_map.tsv"
OUT_JSON = "crawler/parsers/agency_config/ehime.json.new"

out = {}
try:
    with open(TSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            name = row["name"]
            out[name] = {
                "enabled": True,
                "entry_url": row["entry_url"] if row["entry_url"] else None,
                "url_includes": [s.strip() for s in row["url_includes"].split(";") if s.strip()],
                "title_keywords": [s.strip() for s in row["title_keywords"].split(";") if s.strip()],
                "css_selectors": [s.strip() for s in row["css_selectors"].split(";") if s.strip()] or ["a[href*='pdf']"],
                "requires_login": row["requires_login"].lower() == "true",
                "dynamic_strategy": row["dynamic_strategy"] if row["dynamic_strategy"] else "network_idle",
                "notes": row.get("notes", "")
            }
    
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Successfully wrote {OUT_JSON}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
