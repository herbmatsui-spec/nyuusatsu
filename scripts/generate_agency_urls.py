import csv
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MASTER_DIR = os.path.join(DATA_DIR, "master")
os.makedirs(MASTER_DIR, exist_ok=True)

INPUT_PATH = os.path.join(MASTER_DIR, "municipality_codes.csv")
OUTPUT_PATH = os.path.join(MASTER_DIR, "agencies_candidates.json")

# typical bid/procurement page paths in Japanese municipality websites
BID_PAGE_PATHS = [
    # Top-level Nyusatsu / Chotatsu
    "/nyusatsu/",
    "/chotatsu/",
    "/nyusatsu.html",
    "/chotatsu.html",
    "/keiyaku/",
    
    # Nested directories
    "/business/nyusatsu/",
    "/business/chotatsu/",
    "/business/keiyaku/",
    "/jigyosha/nyusatsu/",
    "/jigyosha/chotatsu/",
    "/jigyosha/keiyaku/",
    
    # Specific departments or sub-categories
    "/soshiki/keiyaku/",
    "/soshiki/chotatsu/",
    "/category/nyusatsu/",
    "/category/chotatsu/",
    
    # Specific typical filename patterns
    "/chotatsu/index.html",
    "/nyusatsu/index.html",
    "/business/nyusatsu/index.html",
    "/business/chotatsu/index.html",
]

def main():
    if not os.path.exists(INPUT_PATH):
        print(f"Error: {INPUT_PATH} not found. Run fetch_municipality_codes.py first.")
        return

    print(f"Reading master list from {INPUT_PATH}...")
    
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        agencies = list(reader)

    candidates_list = []

    for agency in agencies:
        base_url = agency["base_url"].strip()
        # Clean double slashes from base URL
        if not base_url.startswith("http"):
            base_url = "https://" + base_url
            
        base_url_clean = base_url.rstrip("/")
        
        # Generate candidates
        candidates = []
        # First candidate is the base url itself
        candidates.append(base_url_clean + "/")
        
        for path in BID_PAGE_PATHS:
            candidates.append(base_url_clean + path)

        candidates_list.append({
            "municipality_code": agency["municipality_code"],
            "name": agency["name"],
            "type": agency["type"],
            "region": agency["region"],
            "base_url": base_url_clean + "/",
            "category": agency["category"],
            "candidates": candidates
        })

    print(f"Generated {len(candidates_list)} agencies with {len(BID_PAGE_PATHS) + 1} URL candidates each.")
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(candidates_list, f, indent=2, ensure_ascii=False)

    print(f"Successfully saved candidates to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
