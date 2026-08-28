"""都道府県別の業種一致度を算出し、crawl_priority テーブルに保存するスクリプト

- `config/target_industries.py` のリストと `bids.industry_category` を照合
- 一致度 = (該当案件数 / 該当都道府県の総案件数) の割合 (0.0-1.0)
- 結果は `CrawlPriority.target_industry_match` に upsert
"""

import sys
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from database.engine import engine
from database.models.crawl_priority import CrawlPriority
from config.target_industries import TARGET_INDUSTRIES


def get_match_ratio(session: Session, pref_code: str) -> float:
    # 総件数
    total = session.execute(
        text("SELECT COUNT(*) FROM bids WHERE prefecture_code = :pc"),
        {"pc": pref_code}
    ).scalar()
    if total == 0:
        return 0.0
    # 一致件数（industry_category に target キーワードが含まれる）
    conditions = []
    for keyword in TARGET_INDUSTRIES:
        conditions.append(f"lower(industry_category) LIKE '%{keyword.lower()}%'")
    where_clause = " OR ".join(conditions)
    query = f"SELECT COUNT(*) FROM bids WHERE prefecture_code = :pc AND ({where_clause})"
    match_cnt = session.execute(text(query), {"pc": pref_code}).scalar()
    return round(match_cnt / total, 3)


def update_industry_match(session: Session):
    # prefecture_code の一覧取得
    pref_codes = [row[0] for row in session.execute("SELECT DISTINCT prefecture_code FROM bids WHERE prefecture_code IS NOT NULL").fetchall()]
    for pc in pref_codes:
        ratio = get_match_ratio(session, pc)
        # upsert to CrawlPriority
        existing = session.execute(select(CrawlPriority).where(CrawlPriority.prefecture_code == pc)).scalar_one_or_none()
        if existing:
            existing.target_industry_match = ratio
        else:
            new = CrawlPriority(
                prefecture_code=pc,
                prefecture_name="",
                agency_count=0,
                target_industry_match=ratio,
                score=0.0,
                status="pending",
            )
            session.add(new)
    session.commit()


def main():
    CrawlPriority.__table__.create(bind=engine, checkfirst=True)
    with Session(engine) as sess:
        update_industry_match(sess)
        print("Industry match ratios updated for prefectures.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error in score_industry_match: {e}", file=sys.stderr)
        sys.exit(1)
