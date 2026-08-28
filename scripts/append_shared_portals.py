import csv
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "agencies.csv")

# List of major shared bidding portals in Japan
SHARED_PORTALS = [
    {
        "name": "かながわ電子入札共同システム",
        "type": "municipality",
        "region": "神奈川県",
        "base_url": "https://www.chotatsu.pref.kanagawa.jp/",
        "target_url": "https://www.chotatsu.pref.kanagawa.jp/index.html",
        "parser_type": "heuristic",
        "frequency": "daily",
        "municipality_code": "", # Empty to prevent UNIQUE constraint violation
        "category": "shared_portal",
        "is_active": "True"
    },
    {
        "name": "ちば電子調達共同システム",
        "type": "municipality",
        "region": "千葉県",
        "base_url": "https://www.chiba-ep.or.jp/",
        "target_url": "https://www.chiba-ep.or.jp/index.html",
        "parser_type": "heuristic",
        "frequency": "daily",
        "municipality_code": "",
        "category": "shared_portal",
        "is_active": "True"
    },
    {
        "name": "埼玉県電子入札共同システム",
        "type": "municipality",
        "region": "埼玉県",
        "base_url": "https://www.nyusatsu.pref.saitama.lg.jp/",
        "target_url": "https://www.nyusatsu.pref.saitama.lg.jp/index.html",
        "parser_type": "heuristic",
        "frequency": "daily",
        "municipality_code": "",
        "category": "shared_portal",
        "is_active": "True"
    },
    {
        "name": "あいち電子調達共同システム",
        "type": "municipality",
        "region": "愛知県",
        "base_url": "https://www.nyusatsu.aichi-collabo.jp/",
        "target_url": "https://www.nyusatsu.aichi-collabo.jp/index.html",
        "parser_type": "heuristic",
        "frequency": "daily",
        "municipality_code": "",
        "category": "shared_portal",
        "is_active": "True"
    },
    {
        "name": "兵庫県電子入札共同運営システム",
        "type": "municipality",
        "region": "兵庫県",
        "base_url": "https://www.nyusatsu.hyogo-collabo.jp/",
        "target_url": "https://www.nyusatsu.hyogo-collabo.jp/index.html",
        "parser_type": "heuristic",
        "frequency": "daily",
        "municipality_code": "",
        "category": "shared_portal",
        "is_active": "True"
    },
    {
        "name": "大阪府・市町村共同入札情報システム",
        "type": "municipality",
        "region": "大阪府",
        "base_url": "https://www.nyusatsu.pref.osaka.jp/",
        "target_url": "https://www.nyusatsu.pref.osaka.jp/index.html",
        "parser_type": "heuristic",
        "frequency": "daily",
        "municipality_code": "",
        "category": "shared_portal",
        "is_active": "True"
    }
]

def main():
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return

    # Read existing rows and filter out any existing shared portals
    clean_rows = []
    portal_names = {p["name"] for p in SHARED_PORTALS}
    
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["name"] not in portal_names and row["category"] != "shared_portal":
                clean_rows.append(row)

    # Add the updated portals
    for portal in SHARED_PORTALS:
        clean_rows.append(portal)

    # Write all back
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "type", "region", "base_url", "target_url", 
            "parser_type", "frequency", "municipality_code", "category", "is_active"
        ])
        writer.writeheader()
        writer.writerows(clean_rows)

    print(f"Successfully cleaned and appended {len(SHARED_PORTALS)} shared portals to {CSV_PATH}.")

if __name__ == "__main__":
    main()
