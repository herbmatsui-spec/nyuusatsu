# 改善点1 ステップ1-8: scripts/fix_ehime_active.py
# このスクリプトは data/agencies.csv を読み込み、愛媛県の自治体の is_active を True に更新します。

import csv
import os
import shutil
from datetime import datetime

def is_ehime(row):
    """行データが愛媛県の自治体であるか判定する"""
    return row.get('region') == '愛媛県'

def activate(row):
    """is_active を True に更新する"""
    row['is_active'] = 'True'
    return row

def run():
    input_path = 'data/agencies.csv'
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    # Backup original file
    backup_path = f"{input_path}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    shutil.copy(input_path, backup_path)
    print(f"Backup created: {backup_path}")

    with open(input_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    updated_rows = []
    count = 0
    for row in rows:
        if is_ehime(row):
            row = activate(row)
            count += 1
        updated_rows.append(row)

    with open(input_path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"Successfully activated {count} agencies in Ehime prefecture.")

if __name__ == "__main__":
    run()
