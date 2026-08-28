import urllib.request
import csv
import io
import os
import sys

# Define target directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MASTER_DIR = os.path.join(DATA_DIR, "master")
os.makedirs(MASTER_DIR, exist_ok=True)

# URL of Code4Fukui open data
URL_PREF = "https://code4fukui.github.io/localgovjp/prefjp-utf8.csv"
URL_MUNI = "https://code4fukui.github.io/localgovjp/localgovjp-utf8.csv"

# Designated cities list
DESIGNATED_CITIES = {
    "札幌市", "仙台市", "さいたま市", "千葉市", "横浜市", "川崎市", "相模原市", "新潟市", "静岡市", "浜松市",
    "名古屋市", "京都市", "大阪市", "堺市", "神戸市", "岡山市", "広島市", "北九州市", "福岡市", "熊本市"
}

# Core cities list
CORE_CITIES = {
    "函館市", "旭川市", "青森市", "八戸市", "盛岡市", "秋田市", "山形市", "福島市", "郡山市", "いわき市",
    "水戸市", "宇都宮市", "前橋市", "高崎市", "川越市", "川口市", "越谷市", "船橋市", "柏市", "八王子市", "横須賀市",
    "富山市", "金沢市", "福井市", "甲府市", "長野市", "松本市",
    "岐阜市", "豊橋市", "岡崎市", "一宮市", "豊田市",
    "大津市", "豊中市", "吹田市", "高槻市", "枚方市", "八尾市", "寝屋川市", "東大阪市", "姫路市", "尼崎市", "明石市", "西宮市", "奈良市", "和歌山市",
    "鳥取市", "松江市", "倉敷市", "呉市", "福山市", "下関市", "高松市", "松山市", "高知市",
    "久留米市", "長崎市", "佐世保市", "大分市", "宮崎市", "鹿児島市", "那覇市"
}

def format_lgcode(code_str):
    if not code_str:
        return ""
    code_str = code_str.strip()
    # Pad to 6 digits (national local government code standard)
    return code_str.zfill(6)

def fetch_csv(url):
    print(f"Fetching: {url}")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8-sig')
        return list(csv.DictReader(io.StringIO(content)))

def main():
    try:
        prefs_raw = fetch_csv(URL_PREF)
        munis_raw = fetch_csv(URL_MUNI)
    except Exception as e:
        print(f"Error fetching data: {e}", file=sys.stderr)
        sys.exit(1)

    agencies = []

    # 1. Process Prefectures
    print("Processing prefectures...")
    for row in prefs_raw:
        name = row.get("pref")
        url = row.get("url")
        lgcode = format_lgcode(row.get("lgcode"))
        
        if name and url:
            agencies.append({
                "municipality_code": lgcode,
                "name": name,
                "type": "municipality",
                "region": name, # Prefecture itself is region
                "base_url": url,
                "category": "prefecture"
            })

    # 2. Process Municipalities
    print("Processing municipalities...")
    for row in munis_raw:
        pref = row.get("pref")
        city = row.get("city")
        url = row.get("url")
        lgcode = format_lgcode(row.get("lgcode"))
        
        if not city or not url:
            continue
            
        # Skip administrative wards of designated cities (they contain space in name, e.g. "札幌市 中央区")
        if " " in city:
            continue
            
        # Determine category
        if city in DESIGNATED_CITIES:
            category = "designated_city"
        elif city in CORE_CITIES:
            category = "core_city"
        elif pref == "東京都" and city.endswith("区"):
            category = "special_ward"
        elif city.endswith("市"):
            category = "city"
        elif city.endswith("町"):
            category = "town"
        elif city.endswith("村"):
            category = "village"
        else:
            category = "city" # fallback

        agencies.append({
            "municipality_code": lgcode,
            "name": f"{pref}{city}" if category in ["town", "village"] else city, # Qualify towns and villages with prefecture name to avoid duplicates
            "type": "municipality",
            "region": pref,
            "base_url": url,
            "category": category
        })

    # Write output to CSV
    output_path = os.path.join(MASTER_DIR, "municipality_codes.csv")
    print(f"Writing parsed agency master to {output_path}...")
    
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["municipality_code", "name", "type", "region", "base_url", "category"])
        writer.writeheader()
        writer.writerows(agencies)

    print(f"Successfully processed {len(agencies)} agencies.")

if __name__ == "__main__":
    main()
