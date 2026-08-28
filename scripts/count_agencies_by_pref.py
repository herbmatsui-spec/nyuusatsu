"""都道府県別の発注機関数を集計し、crawl_priority テーブルへ登録するスクリプト

- SQLite データベース: bids_system.db（SQLAlchemy エンジン `database.engine` を使用）
- 集計対象: bids テーブルの organization_name を prefecture_code 別に重複排除してカウント
- 結果は `CrawlPriority` モデル（database.models.crawl_priority）へ upsert
- テーブルが未作成の場合は SQLAlchemy の metadata で自動作成
"""

import sys
from collections import defaultdict

from sqlalchemy import select, insert, update
from sqlalchemy.orm import Session

# プロジェクト固有のエンジンとモデルインポート
from database.engine import engine
from database.models.crawl_priority import CrawlPriority


def count_agencies_by_prefecture(session: Session):
    """bids テーブルから prefecture_code 別に organization_name のユニーク数を取得"""
    # bids テーブルは直接 SQL でアクセス（SQLAlchemy のモデルが存在しないため）
    result = session.execute(
        "SELECT prefecture_code, COUNT(DISTINCT organization_name) FROM bids WHERE prefecture_code IS NOT NULL GROUP BY prefecture_code"
    )
    counts = {row[0]: row[1] for row in result.fetchall()}
    return counts


def upsert_priority(session: Session, counts: dict):
    for pref_code, agency_cnt in counts.items():
        # 既存レコード検索
        existing = session.execute(
            select(CrawlPriority).where(CrawlPriority.prefecture_code == pref_code)
        ).scalar_one_or_none()
        if existing:
            existing.agency_count = agency_cnt
            existing.updated_at = None  # SQLAlchemy が onupdate を自動で更新
        else:
            new = CrawlPriority(
                prefecture_code=pref_code,
                prefecture_name="",
                agency_count=agency_cnt,
                target_industry_match=0.0,
                score=0.0,
                status="pending",
            )
            session.add(new)
    session.commit()


def main():
    # テーブルが無い場合は作成
    CrawlPriority.__table__.create(bind=engine, checkfirst=True)
    with Session(engine) as sess:
        counts = count_agencies_by_prefecture(sess)
        upsert_priority(sess, counts)
        print("Prefecture agency counts updated:")
        for pref, cnt in counts.items():
            print(f"  {pref}: {cnt}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error during count_agencies_by_pref: {e}", file=sys.stderr)
        sys.exit(1)
