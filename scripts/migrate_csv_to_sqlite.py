import os
import logging
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import Base, Bid, Industry, Region
from database.config import DATABASE_URL
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_budget_amount(budget_str):
    """
    予算文字列を数値（円単位）に変換する。
    例: '1,500万円' -> 15000000
    """
    if not budget_str or budget_str == "不明" or budget_str == "記載なし":
        return None
    
    # 数字以外を除去して抽出
    # 簡易的な実装：数値部分を抽出し、単位に基づいて計算
    try:
        amount_match = re.search(r'(\d[\d,.]*)', budget_str)
        if not amount_match:
            return None
            
        value = float(amount_match.group(1).replace(',', ''))
        
        if '万円' in budget_str:
            return int(value * 10000)
        elif '千円' in budget_str:
            return int(value * 1000)
        elif '億円' in budget_str:
            return int(value * 100000000)
        else:
            return int(value)
    except Exception as e:
        logger.warning(f"Could not parse budget '{budget_str}': {e}")
        return None

def parse_date(date_str):
    """
    日付文字列を datetime.date に変換する。
    CSV形式に合わせて調整が必要。
    """
    if not date_str or date_str == "不明" or date_str == "記載なし":
        return None
    
    # 簡易的なパース (YYYY-MM-DD or YYYY/MM/DD)
    try:
        # 日付形式の正規化を試みる
        normalized = date_str.replace('/', '-').strip()
        return datetime.strptime(normalized, "%Y-%m-%d").date()
    except Exception:
        try:
            # 他の形式 (例: 2024-4-1)
            return pd.to_datetime(date_str).date()
        except Exception as e:
            logger.warning(f"Could not parse date '{date_str}': {e}")
            return None

def migrate():
    csv_path = "./bid_ledger.csv"
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        return

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} records from {csv_path}")

        # CSVのカラム名とモデルのマッピング (bid_processor.py の出力に合わせる)
        # CSV: 解析日時, ファイル名, 予算, 参加資格, 納期, 成果物, リスク, 備考
        
        for index, row in df.iterrows():
            filename = str(row.get("ファイル名", ""))
            if not filename:
                continue

            # 重複チェック
            existing_bid = session.query(Bid).filter_by(filename=filename).first()
            if existing_bid:
                continue

            # 予算の数値化
            budget_text = str(row.get("予算", ""))
            budget_amount = parse_budget_amount(budget_text)

            # 納期から日付を抽出（簡易的に1つ目の日付を採用）
            deadline_text = str(row.get("納期", ""))
            # 本来はここで公告日や締切日を抽出するロジックが必要だが、
            # 既存CSVに日付カラムがない場合は現在日時などを入れるかNoneにする
            
            new_bid = Bid(
                filename=filename,
                project_name=filename, # CSVに案件名がないためファイル名を代用
                budget=budget_text,
                budget_amount=budget_amount,
                qualifications=str(row.get("参加資格", "")),
                deadline=deadline_text,
                full_text=str(row.get("成果物", "")), # 暫定的に成果物をフルテキストに
                analyzed_at=datetime.utcnow()
            )
            session.add(new_bid)

        session.commit()
        logger.info("Migration completed successfully.")

    except Exception as e:
        session.rollback()
        logger.error(f"Migration failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
