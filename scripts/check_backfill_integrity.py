#!/usr/bin/env python
"""
バックフィルデータ整合性チェックスクリプト

バックフィル実行後にデータ品質をチェックし、レポートを出力する。
"""
import sys
import json
from datetime import datetime

from database.session import get_db
from database.models import Bid, BackfillJob
from services.backfill_dedup import BackfillDedupService


def main():
    import argparse
    parser = argparse.ArgumentParser(description="バックフィルデータ整合性チェック")
    parser.add_argument("--job-id", type=int, help="特定ジョブIDをチェック")
    parser.add_argument("--output", type=str, help="出力ファイルパス (JSON)")
    parser.add_argument("--fix", action="store_true", help="重複を自動修正")
    parser.add_argument("--dry-run", action="store_true", help="修正を実行せず対象のみ表示")
    args = parser.parse_args()

    service = BackfillDedupService()

    try:
        if args.job_id:
            print(f"=== Job {args.job_id} 品質レポート ===")
            report = service.generate_quality_report(args.job_id)
            print(json.dumps(report, indent=2, ensure_ascii=False))

            # 欠落フィールド補完
            if not args.dry_run:
                print("\n=== 欠落フィールド補完実行 ===")
                completed = service.backfill_missing_fields(args.job_id, dry_run=args.dry_run)
                print(f"補完結果: {completed}")
        else:
            print("=== 全体データ整合性チェック ===")
            integrity = service.check_integrity()
            print(json.dumps(integrity, indent=2, ensure_ascii=False))

            if args.fix and not args.dry_run:
                print("\n=== 重複自動修正実行 ===")
                result = service.merge_duplicates(dry_run=args.dry_run)
                print(f"修正結果: {result}")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(report if args.job_id else integrity, f, indent=2, ensure_ascii=False)
            print(f"\nレポートを保存: {args.output}")

        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())