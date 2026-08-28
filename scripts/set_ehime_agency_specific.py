# 改善点2 ステップ53: scripts/set_ehime_agency_specific.py
# 愛媛県自治体の parser_type を 'agency_specific' に更新します。

import csv
import os
from datetime import datetime

def run():
    input_path = 'data/agencies.csv'
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    # Backup
    backup_path = f"{input_path}_parser_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    import shutil
    shutil.copy(input_path, backup_path)
    print(f"Backup created: {backup_path}")

    with open(input_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    updated_rows = []
    count = 0
    for row in rows:
        if row.get('region') == '愛媛県':
            row['parser_type'] = 'agency_specific'
            count += 1
        updated_rows.append(row)

    with open(input_path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"Successfully updated {count} agencies to 'agency_specific' in Ehime prefecture.")

if __name__ == "__main__":
    run()
