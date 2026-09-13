"""都道府県マスタとクロールソースをDBに投入する。

実行方法:
    python scripts/seed_prefectures.py
"""
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database.engine import engine, SessionLocal
from database.base import Base
from database.models import Prefecture, BidSource
import database.models  # 全モデルを登録して create_all の対象にする
from database.seeders.prefecture_seeder import (
    PREFECTURES,
    HOKKAIDO_SOURCES,
    geps_source_for,
)


def create_tables() -> None:
    # prefectures / bid_sources / crawl_jobs 等の未作成テーブルを作成
    Base.metadata.create_all(bind=engine)


def seed_prefectures(session) -> int:
    count = 0
    for code, name, kana, region, priority, official_url in PREFECTURES:
        existing = session.query(Prefecture).filter_by(code=code).first()
        if existing:
            continue
        session.add(Prefecture(
            code=code, name=name, kana_name=kana,
            region_code=region, priority=priority,
            official_url=official_url, is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ))
        count += 1
    session.commit()
    return count


def seed_hokkaido_sources(session) -> int:
    """北海道のみの専用ソース（web+geps）を登録。"""
    hokkaido = session.query(Prefecture).filter_by(code="01").first()
    if not hokkaido:
        return 0
    count = 0
    for source_type, url, parser_type, notes in HOKKAIDO_SOURCES:
        if session.query(BidSource).filter_by(prefecture_id=hokkaido.id, url=url).first():
            continue
        session.add(BidSource(
            prefecture_id=hokkaido.id,
            source_type=source_type,
            url=url,
            url_pattern=None,
            parser_type=parser_type,
            css_selectors=None,
            requires_login=False,
            username=None,
            password=None,
            last_crawled_at=None,
            crawl_interval_hours=24,
            is_active=True,
            notes=notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ))
        count += 1
    session.commit()
    return count


def seed_all_sources(session) -> int:
    """全47都道府県の GEPS ソースを統一フォーマットで登録（北海道webは除く）。"""
    count = 0
    for code, name, kana, region, priority, official_url in PREFECTURES:
        pref = session.query(Prefecture).filter_by(code=code).first()
        if not pref:
            continue
        source_type, url, parser_type, notes = geps_source_for(code, name)
        if session.query(BidSource).filter_by(prefecture_id=pref.id, url=url).first():
            continue
        session.add(BidSource(
            prefecture_id=pref.id,
            source_type=source_type,
            url=url,
            url_pattern=None,
            parser_type=parser_type,
            css_selectors=None,
            requires_login=False,
            username=None,
            password=None,
            last_crawled_at=None,
            crawl_interval_hours=24,
            is_active=True,
            notes=notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ))
        count += 1
    session.commit()
    return count


def main() -> None:
    create_tables()
    session = SessionLocal()
    try:
        p = seed_prefectures(session)
        s = seed_hokkaido_sources(session)
        a = seed_all_sources(session)
        total = session.query(Prefecture).count()
        total_src = session.query(BidSource).count()
        hok = session.query(BidSource).filter_by(
            prefecture_id=session.query(Prefecture).filter_by(code="01").first().id
        ).count()
        print(f" prefecture inserted (new): {p}")
        print(f" hokkaido bid_source inserted (new): {s}")
        print(f" all geps bid_source inserted (new): {a}")
        print(f" total prefectures: {total}")
        print(f" total bid_sources: {total_src}")
        print(f" hokkaido bid_sources: {hok}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
