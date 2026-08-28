import pandas as pd
import json
from sqlalchemy.orm import Session
from database.engine import get_session
from database.repositories.bid_repository import BidRepository
from datetime import datetime

def migrate_csv_to_db(csv_path: str):
    """
    bid_ledger.csv のデータをデータベースに移行する。
    """
    if not pandas.io.common.file_exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return

    df = pd.read_csv(csv_path)
    
    with get_session() as session:
        repo = BidRepository(session)
        count = 0
        
        for _, row in df.iterrows():
            # 重複チェック (filename)
            filename = str(row.get("ファイル名", "unknown"))
            if repo.get_by_filename(filename):
                continue

            # データのクレンジングとマッピング
            # リスト形式のデータ (参加資格, リスク) は文字列で保存されている想定
            # もし `; ` 区切りならそのまま Text 型へ。
            
            bid_data = {
                "filename": filename,
                "analyzed_at": datetime.strptime(row["解析日時"], "%Y-%m-%d %H:%M:%S") if "解析日時" in row else datetime.utcnow(),
                "budget": str(row.get("予算", "不明")),
                "qualifications": str(row.get("参加資格", "不明")),
                "deadline": str(row.get("納期", "不明")),
                "deliverables": str(row.get("成果物", "不明")),
                "key_risks": str(row.get("リスク", "不明")),
                "notes": str(row.get("備考", "")),
                "current_status": "未確認"
            }
            
            repo.create(bid_data)
            count += 1
        
        session.commit()
        print(f"Successfully migrated {count} records from {csv_path} to database.")

if __name__ == "__main__":
    # 既存の CSV パス
    CSV_PATH = "./bid_ledger.csv"
    migrate_csv_to_db(CSV_PATH)
