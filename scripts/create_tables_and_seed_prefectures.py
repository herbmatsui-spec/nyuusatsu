"""Create all tables and seed the Prefecture table with Japan's 47 prefectures.
Run with:
    python -m scripts.create_tables_and_seed_prefectures
"""
import sys
from pathlib import Path

# Ensure project root is in PYTHONPATH
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from database import Base, engine
from database.models import Prefecture
from sqlalchemy.orm import Session

prefectures = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

def main() -> None:
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    with Session(bind=engine) as session:
        existing = session.query(Prefecture).count()
        if existing:
            print(f"Prefecture table already has {existing} records. Skipping seed.")
            return
        for name in prefectures:
            session.add(Prefecture(name=name))
        session.commit()
        print(f"Inserted {len(prefectures)} prefectures.")

if __name__ == "__main__":
    main()
