import json
import os
import urllib.request
import urllib.parse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# Reconfigure stdout for Japanese encoding on Windows console
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MASTER_DIR = os.path.join(DATA_DIR, "master")

INPUT_PATH = os.path.join(MASTER_DIR, "agencies_candidates.json")
OUTPUT_PATH = os.path.join(DATA_DIR, "agencies.csv")

# Keywords that indicate a bidding/procurement page
NYUSATSU_KEYWORDS = ["入札", "調達", "公示", "公告", "契約", "発注"]

def check_url(url):
    """
    Check if a URL is valid (200 OK) and contains bidding keywords.
    Returns (is_valid, has_keywords)
    """
    req = urllib.request.Request(
        url, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3'
        }
    )
    try:
        # 5 seconds timeout
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                return False, False
            
            # Read first 50KB of content to scan for keywords
            content_bytes = response.read(50000)
            
            # Try decoding
            content_text = ""
            for encoding in ['utf-8', 'shift_jis', 'euc-jp', 'cp932']:
                try:
                    content_text = content_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if not content_text:
                return True, False # Got 200 but could not decode content
                
            has_keywords = any(kw in content_text for kw in NYUSATSU_KEYWORDS)
            return True, has_keywords
    except Exception:
        return False, False

def validate_agency(agency):
    """
    Validates candidates for a single agency sequentially to avoid overloading its server.
    """
    name = agency["name"]
    candidates = agency["candidates"]
    category = agency["category"]
    
    best_url = None
    
    # Check candidates (excluding the base URL candidate itself if possible, to find the specific nyusatsu page)
    # The first candidate is always the base URL (e.g. index page), other 19 are sub-pages.
    base_url_candidate = candidates[0]
    subpage_candidates = candidates[1:]
    
    # 1. Test subpages first to find the direct nyusatsu page
    for url in subpage_candidates:
        is_valid, has_keywords = check_url(url)
        if is_valid and has_keywords:
            best_url = url
            break
        elif is_valid and not best_url:
            # Fallback to a valid page even if keywords weren't fully detected in first 50KB
            best_url = url
            
    # 2. If no subpage worked, check the base URL as last resort
    if not best_url:
        is_valid, has_keywords = check_url(base_url_candidate)
        if is_valid:
            best_url = base_url_candidate

    if best_url:
        print(f"[SUCCESS] {name} ({category}) -> {best_url}")
        return {
            "name": name,
            "type": agency["type"],
            "region": agency["region"],
            "base_url": agency["base_url"],
            "target_url": best_url,
            "parser_type": "heuristic",
            "frequency": "daily" if category in ["prefecture", "designated_city", "core_city", "special_ward"] else "weekly",
            "municipality_code": agency["municipality_code"],
            "category": category,
            "is_active": "True"
        }
    else:
        # Unreachable or small town with no bidding page
        print(f"[INACTIVE] {name} ({category}) -> No bidding page found.")
        return {
            "name": name,
            "type": agency["type"],
            "region": agency["region"],
            "base_url": agency["base_url"],
            "target_url": agency["base_url"], # fallback to base_url
            "parser_type": "heuristic",
            "frequency": "weekly",
            "municipality_code": agency["municipality_code"],
            "category": category,
            "is_active": "False" # Deactivated by default
        }

def main():
    if not os.path.exists(INPUT_PATH):
        print(f"Error: {INPUT_PATH} not found.")
        return

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        agencies = json.load(f)

    # Filter out empty/invalid agencies
    agencies = [a for a in agencies if a.get("base_url")]

    print(f"Starting URL validation for {len(agencies)} agencies using ThreadPoolExecutor...")
    
    results = []
    # Use 30 concurrent threads
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(validate_agency, agency): agency for agency in agencies}
        
        for future in as_completed(futures):
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                agency = futures[future]
                print(f"[ERROR] Failed to validate {agency['name']}: {e}", file=sys.stderr)

    # Sort results by municipality_code to keep CSV organized
    results.sort(key=lambda x: x["municipality_code"])

    # Write back to data/agencies.csv
    print(f"Writing final validation results to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "type", "region", "base_url", "target_url", 
            "parser_type", "frequency", "municipality_code", "category", "is_active"
        ])
        writer.writeheader()
        writer.writerows(results)

    print("URL validation completed successfully.")

if __name__ == "__main__":
    main()
