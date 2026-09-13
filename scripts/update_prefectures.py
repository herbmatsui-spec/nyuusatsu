#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
都道府県マスタデータの更新スクリプト（UPSERT）
- data/prefectures.csv を読み込み、prefectures テーブルを更新・挿入
- 既存の code があれば更新、無ければ挿入
"""

import csv
import sqlite3
import os
from datetime import datetime

def main():
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'prefectures.csv')
    db_path = os.path.join(os.path.dirname(__file__), '..', 'bids_system.db')
    
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return 1
        
    # Read CSV data
    prefectures = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prefectures.append((
                int(row['id']),
                row['name'],
                row['code'],
                row['kana_name'],
                row['region_code'],
                datetime.now(),  # updated_at
                datetime.now()   # created_at (will be ignored on update if we set correctly)
            ))
    
    # Connect to DB
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Upsert: insert or update based on code (unique)
        # We'll use INSERT OR REPLACE, but we need to preserve id? 
        # Better: update existing, insert new.
        # First, update existing
        update_sql = """
            UPDATE prefectures
            SET name = ?, kana_name = ?, region_code = ?, updated_at = ?
            WHERE code = ?
        """
        insert_sql = """
            INSERT INTO prefectures (id, name, code, kana_name, region_code, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        updated_count = 0
        inserted_count = 0
        
        for pref_id, name, code, kana, region, updated_at, created_at in prefectures:
            # Try update
            cursor.execute(update_sql, (name, kana, region, updated_at, code))
            if cursor.rowcount > 0:
                updated_count += 1
            else:
                # If no rows updated, insert
                cursor.execute(insert_sql, (pref_id, name, code, kana, region, created_at, updated_at))
                inserted_count += 1
        
        conn.commit()
        print(f"Updated: {updated_count} prefectures")
        print(f"Inserted: {inserted_count} prefectures")
        print(f"Total processed: {updated_count + inserted_count}")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM prefectures")
        count = cursor.fetchone()[0]
        print(f"Total prefectures in DB: {count}")
        
        return 0
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        return 1
    finally:
        conn.close()

if __name__ == '__main__':
    exit(main())