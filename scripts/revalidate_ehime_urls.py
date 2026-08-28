# 改善点1 ステップ14-21: scripts/revalidate_ehime_urls.py
# 愛媛県自治体のURLを再検証し、最適な入札情報ページを特定して agencies.csv を更新します。

import json
import os
import urllib.request
import urllib.parse
import csv
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# Reconfigure stdout for Japanese encoding on Windows console
sys.stdout.reconfigure(encoding='utf-8')

# 既存の validate_agency_urls.py からキーワード設定を借用
NYUSATSU_KEYWORDS = ["入札", "調達", "公示", "公告", "契約", "発注"]

# 愛媛県主要自治体の検証用候補URLリスト (Step 15)
EHIME_AGENCIES_CANDIDATES = {
    "松山市": [
        "https://www.city.matsuyama.ehime.jp/",
        "https://www.city.matsuyama.ehime.jp/shisei/shiseijoho/nyusatsu/",
        "https://www.city.matsuyama.ehime.jp/shisei/shiseijoho/nyusatsu/koukoku/",
    ],
    "今治市": [
        "https://www.city.imabari.ehime.jp/",
        "https://www.city.imabari.ehime.jp/soshiki/somusho/nyusatsu/index.html",
    ],
    "宇和島市": [
        "https://www.city.uwajima.ehime.jp/",
        "https://www.city.uwajima.ehime.jp/shisei/nyusatsu/index.html",
    ],
}

def check_url(url):
    """URLが有効(200 OK)で入札キーワードを含むかチェックする"""
    req = urllib.request.Request(
        url, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                return False, False
            content_bytes = response.read(50000)
            content_text = ""
            for encoding in ['utf-8', 'shift_jis', 'euc-jp', 'cp932']:
                try:
                    content_text = content_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if not content_text:
                return True, False
            has_keywords = any(kw in content_text for kw in NYUSATSU_KEYWORDS)
            return True, has_keywords
    except Exception:
        return False, False

def update_csv_row(row, best_url, has_keywords):
    """CSVの行を更新する"""
    row['target_url'] = best_url
    return row

def run(dry_run=False):
    input_path = 'data/agencies.csv'
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    # Backup
    backup_path = f"{input_path}_reval_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    shutil.copy(input_path, backup_path)
    print(f"Backup created: {backup_path}")

    with open(input_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    updated_rows = []
    for row in rows:
        name = row['name']
        if row.get('region') == '愛媛県' and name in EHIME_AGENCIES_CANDIDATES:
            candidates = EHIME_AGENCIES_CANDIDATES[name]
            best_url = row['target_url']
            found_keyword = False
            
            print(f"Revalidating {name}...")
            for url in candidates:
                is_valid, has_keywords = check_url(url)
                if is_valid and has_keywords:
                    best_url = url
                    found_keyword = True
                    break
                elif is_valid and not found_keyword:
                    best_url = url
            
            if dry_run:
                print(f"[DRY-RUN] {name}: {row['target_url']} -> {best_url} (Keywords: {found_keyword})")
            
            row = update_csv_row(row, best_url, found_keyword)
        
        updated_rows.append(row)

    if not dry_run:
        with open(input_path, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)
        print("CSV updated successfully.")
    else:
        print("Dry-run completed. No changes made to CSV.")

if __name__ == "__main__":
    import sys
    is_dry = "--dry-run" in sys.argv
    run(dry_run=is_dry)
