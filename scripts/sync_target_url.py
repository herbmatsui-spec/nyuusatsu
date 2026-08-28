import csv, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

CONFIG_PATH = "crawler/parsers/agency_config/ehime.json"
CSV_PATH = "data/agencies.csv"
CSV_NEW_PATH = "data/agencies.csv.new"

try:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)

    rows = []
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for r in reader:
            # 愛媛県の自治体であり、かつ設定ファイルにエントリーURLが存在する場合に更新
            if r["region"] == "愛媛県" and r["name"] in cfg:
                entry_url = cfg[r["name"]].get("entry_url")
                if entry_url:
                    r["target_url"] = entry_url
            rows.append(r)

    with open(CSV_NEW_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Successfully wrote {CSV_NEW_PATH}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
