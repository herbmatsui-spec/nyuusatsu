#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""都道府県データに基づき agencies テーブルへレコードを投入する。

手順:
1. prefectures テーブルから都道府県名を取得
2. data/prefecture_urls.csv から都道府県名と市区町村コードのマッピングを読み込む
3. 既存の都道府県レコード (category_id=2) を削除
4. 各都道府県に対して agencies レコードを挿入
   - name: 都道府県名
   - type: 空文字列 (後段階で設定)
   - region: 空文字列 (後段階で設定)
   - base_url: 空文字列 (後段階で設定)
   - municipality_code: 都道府県の市区町村コード (6桁)
   - category_id: 2 (都道府県)
   - priority_level: 1 (中)
   - system_type: 空文字列 (後段階で設定)
   - created_at, updated_at: 現在タイムスタンプ
"""

import csv
import os
import sys
from datetime import datetime

# プロジェクトルートをパスに追加 (このスクリプトの親の親ディレクトリ)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy.orm import Session
from database.session import SessionLocal
from database.engine import engine
from database.base import Base
from database.models import Agency, Prefecture

def load_prefecture_municipality_code_mapping(csv_path: str) -> dict:
    """CSVから都道府県名 -> 市区町村コードのマッピングを読み込む。
    CSVのフォーマット: municipality_code,name,base_url,bid_url_pattern,bid_system,parser_type
    """
    mapping = {}
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:  # UTF-8 with BOM stripping
            reader = csv.DictReader(f)
            for row in reader:
                name = row['name'].strip()
                code = row['municipality_code'].strip()
                if name and code:
                    mapping[name] = code
    except Exception as e:
        print(f"WARNING: Failed to read {csv_path}: {e}", file=sys.stderr)
    return mapping

def main() -> None:
    # テーブルが存在することを確認（存在しなければ作成）
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # 既存の都道府県レコードを削除
        deleted = db.query(Agency).filter(Agency.category_id == 2).delete(synchronize_session=False)
        db.commit()
        print(f"Deleted {deleted} existing prefecture agency records.")

        # 都道府県名 -> 市区町村コードのマッピングをロード
        csv_path = os.path.join(PROJECT_ROOT, 'data', 'prefecture_urls.csv')
        pref_to_muni = load_prefecture_municipality_code_mapping(csv_path)
        if not pref_to_muni:
            print("WARNING: Could not load municipality code mapping from CSV. Falling back to empty municipality_code.")
            pref_to_muni = {}

        # 全都道府県を取得
        prefectures = db.query(Prefecture).order_by(Prefecture.code).all()
        if not prefectures:
            print("ERROR: No prefectures found in the database. Run seed_prefectures.py first.")
            sys.exit(1)

        inserted = 0
        for pref in prefectures:
            muni_code = pref_to_muni.get(pref.name, "")
            # マッピングが見つからない場合は空文字列とする（レコードは挿入されるが、後段階でURLが設定されない可能性がある）
            agency = Agency(
                name=pref.name,
                type="",  # 後段階で設定
                region="",  # 後段階で設定
                base_url="",  # 後段階で設定 (ステップ18)
                municipality_code=muni_code,
                category_id=2,  # 都道府県 (ステップ16)
                priority_level=1,  # 中 (デフォルト) (ステップ17)
                system_type="",  # 後段階で設定
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(agency)
            inserted += 1

        db.commit()
        print(f"Inserted {inserted} prefecture agency records.")

        # 確認
        total = db.query(Agency).filter(Agency.category_id == 2).count()
        print(f"Total agencies with category_id=2: {total}")

        # サンプル表示（最初の3件）
        samples = db.query(Agency).filter(Agency.category_id == 2).order_by(Agency.id).limit(3).all()
        print("Sample inserted agencies:")
        for a in samples:
            print(f"  ID: {a.id}, Name: {a.name}, Municipality Code: {a.municipality_code or '(empty)'}, Base URL: '{a.base_url or ''}', Priority Level: {a.priority_level}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
