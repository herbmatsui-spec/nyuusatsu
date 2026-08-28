"""優先度マトリクスを算出し、CrawlPriority テーブルにスコアとステータスを保存するスクリプト

- 事前に `count_agencies_by_pref.py` と `score_industry_match.py` が実行され、`agency_count` と `target_industry_match` が設定済みであることを前提とする
- `priority_scorer.calc_score` でスコア算出
- スコア上位 10 件 (例) を `status='active'` にし、残りは `pending`
"""

import sys
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from database.engine import engine
from database.models.crawl_priority import CrawlPriority
from services.priority_scorer import calc_score

TOP_N = 10  # アクティブにする上位件数（要件に応じて調整）


def compute_and_update(session: Session):
    # すべてのレコードを取得
    rows = session.execute(select(CrawlPriority)).scalars().all()
    # スコア計算
    for row in rows:
        row.score = calc_score(row.agency_count, row.target_industry_match)
    # ソートして上位 TOP_N を active に、残りは pending に設定
    sorted_rows = sorted(rows, key=lambda r: r.score, reverse=True)
    for i, row in enumerate(sorted_rows):
        if i < TOP_N:
            row.status = "active"
        else:
            row.status = "pending"
    session.commit()


def main():
    with Session(engine) as sess:
        compute_and_update(sess)
        print("Priority matrix computed and statuses updated.")
        for r in sess.execute(select(CrawlPriority).order_by(CrawlPriority.score.desc())).scalars().all():
            print(f"{r.prefecture_code}: score={r.score:.2f}, status={r.status}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error in build_priority_matrix: {e}", file=sys.stderr)
        sys.exit(1)
