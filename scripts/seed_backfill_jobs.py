#!/usr/bin/env python
"""
バックフィルジョブ初期投入スクリプト

クロール済みの発注機関に対して、過去N年分のバックフィルジョブを一括作成する。

Usage:
    python scripts/seed_backfill_jobs.py [--years YEARS] [--agency-id AGENCY_ID] [--category CATEGORY] [--dry-run]
"""
import argparse
import sys
from datetime import datetime, timedelta
from typing import List, Optional

from database.session import get_db
from database.models import Agency, AgencyInventory, BidSource, BackfillJob, BackfillJobStatus, AgencyCategory
from services.backfill_service import BackfillService


def get_target_agencies(
    db,
    agency_id: Optional[int] = None,
    category: Optional[str] = None,
    only_crawled: bool = True,
    only_active_sources: bool = True,
) -> List[Agency]:
    """バックフィル対象の発注機関を取得"""
    query = db.query(Agency)

    if agency_id:
        query = query.filter(Agency.id == agency_id)

    if category:
        query = query.join(AgencyCategory).filter(AgencyCategory.name == category)

    if only_crawled:
        # AgencyInventory.is_crawled=True の機関のみ
        crawled_agency_names = db.query(AgencyInventory.agency_name).filter(
            AgencyInventory.is_crawled == True
        ).subquery()
        query = query.filter(Agency.name.in_(crawled_agency_names))

    if only_active_sources:
        # BidSource.is_active=True の機関（prefecture_id ベース）
        active_prefecture_ids = db.query(BidSource.prefecture_id).filter(
            BidSource.is_active == True
        ).subquery()
        # Prefecture.id -> Agency のマッピングが必要なため、ここではスキップ
        pass

    return query.all()


def main():
    parser = argparse.ArgumentParser(description="バックフィルジョブ初期投入")
    parser.add_argument("--years", type=int, default=2, help="遡及年数 (default: 2)")
    parser.add_argument("--agency-id", type=int, help="特定の機関IDのみ対象")
    parser.add_argument("--category", type=str, help="カテゴリ名でフィルタ (国/都道府県/市区町村/外郭団体)")
    parser.add_argument("--dry-run", action="store_true", help="実際にジョブ作成せず対象のみ表示")
    parser.add_argument("--include-uncrawled", action="store_true", help="未クロール機関も含める")
    parser.add_argument("--start-date", type=str, help="開始日 (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="終了日 (YYYY-MM-DD)")

    args = parser.parse_args()

    db = next(get_db())
    service = BackfillService()

    try:
        print(f"=== バックフィルジョブ投入 ===")
        print(f"遡及期間: {args.years}年")
        if args.agency_id:
            print(f"対象機関ID: {args.agency_id}")
        if args.category:
            print(f"対象カテゴリ: {args.category}")
        if args.start_date:
            print(f"開始日: {args.start_date}")
        if args.end_date:
            print(f"終了日: {args.end_date}")
        if args.dry_run:
            print("モード: DRY-RUN (ジョブ作成なし)")
        print()

        agencies = get_target_agencies(
            db,
            agency_id=args.agency_id,
            category=args.category,
            only_crawled=not args.include_uncrawled,
        )

        print(f"対象機関数: {len(agencies)}")
        for a in agencies:
            print(f"  - {a.name} (id={a.id}, type={a.type}, priority={a.priority_level})")

        if not agencies:
            print("対象機関が見つかりません")
            return 0

        # 日付パース
        start_date = None
        end_date = None
        if args.start_date:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        if args.end_date:
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

        print()
        created_count = 0
        skipped_count = 0

        for agency in agencies:
            if args.dry_run:
                period_start = start_date or (datetime.utcnow().date() - timedelta(days=args.years * 365))
                period_end = end_date or datetime.utcnow().date()
                print(f"  DRY-RUN: {agency.name} (id={agency.id}) - 期間: {period_start} 〜 {period_end}")
                created_count += 1
                continue

            try:
                job = service.create_job(
                    agency_id=agency.id,
                    years=args.years,
                    start_date=start_date,
                    end_date=end_date,
                )
                if job.status == BackfillJobStatus.PENDING:
                    print(f"  CREATED: {agency.name} (id={agency.id}) - job_id={job.id}")
                    created_count += 1
                else:
                    print(f"  SKIP: {agency.name} (id={agency.id}) - 既存ジョブ (job_id={job.id}, status={job.status.value})")
                    skipped_count += 1
            except Exception as e:
                print(f"  ERROR: {agency.name} (id={agency.id}) - {e}")
                skipped_count += 1

        print()
        print(f"=== 結果 ===")
        print(f"作成: {created_count} 件")
        print(f"スキップ/エラー: {skipped_count} 件")
        if args.dry_run:
            print("※ DRY-RUN モードのため実際のジョブは作成されていません")
            print("   実行するには --dry-run を外して再実行してください")

        return 0

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())