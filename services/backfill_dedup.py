"""重複排除・データ整合性修正サービス

バックフィルで取得したデータの重複検出・排除、欠落フィールド補完、異常値検出を行う
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import date
from collections import defaultdict

from database.session import get_db
from database.models import Bid, BackfillJob
from services.bid_storage_service import BidStorageService
from services.bid_normalizer import BidNormalizer
from crawler.utils.date_parser import parse_date_string

logger = logging.getLogger(__name__)


class BackfillDedupService:
    """バックフィル重複排除・整合性修正サービス"""

    def __init__(self):
        self.storage = BidStorageService()
        self.normalizer = BidNormalizer()

        # 異常値検出ルール
        self.ANOMALY_RULES = {
            "budget_amount": {"min": 1000, "max": 10_000_000_000},  # 1千円〜100億
            "announcement_date": {"past_years_max": 10, "future_days_max": 365},
            "award_rate": {"min": 0.0, "max": 100.0},
        }

    def find_duplicates(self) -> Dict[str, List[Bid]]:
        """source_url ベースで重複を検出

        Returns:
            {source_url: [Bid, ...]} の辞書（2件以上の場合のみ）
        """
        db = next(get_db())
        try:
            # source_url でグループ化して重複を検出
            from sqlalchemy import func
            dup_sub = db.query(Bid.source_url).group_by(Bid.source_url).having(
                func.count(Bid.id) > 1
            ).subquery()

            dup_bids = db.query(Bid).filter(Bid.source_url.in_(
                db.query(dup_sub.c.source_url)
            )).all()

            # source_url ごとにグループ化
            groups = defaultdict(list)
            for bid in dup_bids:
                if bid.source_url:
                    groups[bid.source_url].append(bid)

            return dict(groups)
        finally:
            db.close()

    def merge_duplicates(self, dry_run: bool = False) -> Dict[str, int]:
        """重複レコードを統合（最新の情報で上書き）

        Args:
            dry_run: True の場合は実際の更新は行わず、統合対象件数のみ返す

        Returns:
            {"merged": 統合件数, "deleted": 削除件数}
        """
        duplicates = self.find_duplicates()
        merged_count = 0
        deleted_count = 0

        db = next(get_db())
        try:
            for source_url, bids in duplicates.items():
                if len(bids) < 2:
                    continue

                # 最新のレコードをマスターとして保持（updated_at でソート）
                bids_sorted = sorted(bids, key=lambda b: b.updated_at or b.created_at, reverse=True)
                master = bids_sorted[0]
                duplicates_to_merge = bids_sorted[1:]

                for dup in duplicates_to_merge:
                    # マスターレコードに欠落情報があれば補完
                    self._merge_bid_data(master, dup)

                    if not dry_run:
                        # 重複レコード削除
                        db.delete(dup)
                        deleted_count += 1
                    merged_count += 1

            if not dry_run:
                db.commit()

            logger.info(f"Merge duplicates: merged={merged_count}, deleted={deleted_count}")
            return {"merged": merged_count, "deleted": deleted_count}
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to merge duplicates: {e}")
            raise
        finally:
            db.close()

    def _merge_bid_data(self, master: Bid, source: Bid):
        """ソースレコードの情報でマスターレコードを補完"""
        fields_to_merge = [
            "budget", "budget_amount", "deadline", "qualifications",
            "deliverables", "organization_name", "industry_category",
            "announcement_date", "awarded_company", "awarded_date",
            "award_rate", "actual_bid_amount", "win_loss_reason",
        ]

        for field in fields_to_merge:
            master_val = getattr(master, field, None)
            source_val = getattr(source, field, None)

            if master_val is None and source_val is not None:
                setattr(master, field, source_val)
                logger.debug(f"Merged {field} from dup {source.id} to master {master.id}")

    def clean_orphans(self, dry_run: bool = False) -> int:
        """孤立レコード（関連なし）のクリーンアップ

        現状では source_url が空のレコードを検出
        """
        db = next(get_db())
        try:
            orphans = db.query(Bid).filter(
                (Bid.source_url == None) | (Bid.source_url == "")
            ).all()

            count = len(orphans)
            if not dry_run and orphans:
                for orphan in orphans:
                    db.delete(orphan)
                db.commit()

            logger.info(f"Clean orphans: found={count}, deleted={count if not dry_run else 0}")
            return count
        finally:
            db.close()

    def check_integrity(self) -> Dict[str, Any]:
        """データ整合性チェック

        Returns:
            チェック結果の辞書
        """
        db = next(get_db())
        try:
            results = {}

            # 重複件数
            dup_groups = self.find_duplicates()
            results["duplicate_groups"] = len(dup_groups)
            results["duplicate_total"] = sum(len(v) for v in dup_groups.values())

            # source_url 未設定
            null_source = db.query(Bid).filter(
                (Bid.source_url == None) | (Bid.source_url == "")
            ).count()
            results["null_source_url"] = null_source

            # 必須フィールド欠落
            required_fields = ["budget_amount", "announcement_date", "organization_name"]
            for field in required_fields:
                count = db.query(Bid).filter(getattr(Bid, field) == None).count()
                results[f"missing_{field}"] = count

            # 異常値検出
            anomalies = self.detect_anomalies()
            results["anomalies"] = anomalies

            return results
        finally:
            db.close()

    def detect_anomalies(self) -> Dict[str, List[Dict]]:
        """異常値検出

        Returns:
            {ルール名: [異常レコード情報, ...]}
        """
        db = next(get_db())
        try:
            anomalies = {}

            # budget_amount 異常
            bids = db.query(Bid).filter(Bid.budget_amount != None).all()
            budget_anomalies = []
            for bid in bids:
                val = bid.budget_amount
                if val < self.ANOMALY_RULES["budget_amount"]["min"] or val > self.ANOMALY_RULES["budget_amount"]["max"]:
                    budget_anomalies.append({"id": bid.id, "value": val, "field": "budget_amount"})
            if budget_anomalies:
                anomalies["budget_amount"] = budget_anomalies

            # announcement_date 異常（未来すぎる、過去すぎる）
            from datetime import date, timedelta
            today = date.today()
            max_past = today - timedelta(days=365 * self.ANOMALY_RULES["announcement_date"]["past_years_max"])
            max_future = today + timedelta(days=self.ANOMALY_RULES["announcement_date"]["future_days_max"])

            bids = db.query(Bid).filter(Bid.announcement_date != None).all()
            date_anomalies = []
            for bid in bids:
                d = bid.announcement_date
                if d < max_past or d > max_future:
                    date_anomalies.append({"id": bid.id, "value": str(d), "field": "announcement_date"})
            if date_anomalies:
                anomalies["announcement_date"] = date_anomalies

            return anomalies
        finally:
            db.close()

    def backfill_missing_fields(self, job_id: int, dry_run: bool = False) -> Dict[str, int]:
        """特定ジョブで取得したレコードの欠落フィールドを補完

        Args:
            job_id: 対象ジョブID
            dry_run: True の場合は実際の更新は行わない

        Returns:
            {フィールド名: 補完件数}
        """
        db = next(get_db())
        try:
            job = db.query(BackfillJob).get(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            # ジョブ期間内に作成/更新されたレコードを対象
            bids = db.query(Bid).filter(
                Bid.created_at >= job.start_date,
                Bid.created_at <= job.end_date,
            ).all()

            completed = defaultdict(int)

            for bid in bids:
                updated = False

                # budget_amount 補完（budget テキストから抽出）
                if bid.budget_amount is None and bid.budget:
                    amount = self.storage._extract_budget_amount(bid.budget)
                    if amount:
                        if not dry_run:
                            bid.budget_amount = amount
                        completed["budget_amount"] += 1
                        updated = True

                # announcement_date 補完
                if bid.announcement_date is None:
                    # deadline や他のフィールドから推定
                    for src_field in ["deadline", "budget", "qualifications", "deliverables"]:
                        src_val = getattr(bid, src_field, None)
                        if src_val:
                            parsed = parse_date_string(str(src_val))
                            if parsed:
                                if not dry_run:
                                    bid.announcement_date = parsed
                                completed["announcement_date"] += 1
                                updated = True
                                break

                # 正規化処理適用
                if bid.organization_name:
                    normalized = self.normalizer.normalize_company_name(bid.organization_name)
                    if normalized != bid.organization_name:
                        if not dry_run:
                            bid.organization_name = normalized
                        completed["organization_name_normalized"] += 1
                        updated = True

                if updated and not dry_run:
                    bid.updated_at = datetime.utcnow()

            if not dry_run:
                db.commit()

            return dict(completed)
        finally:
            db.close()

    def generate_quality_report(self, job_id: Optional[int] = None) -> Dict[str, Any]:
        """品質レポート生成

        Args:
            job_id: 特定ジョブの場合はそのジョブのみ、None の場合は全体

        Returns:
            品質レポート辞書
        """
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "job_id": job_id,
        }

        if job_id:
            # 特定ジョブのレポート
            db = next(get_db())
            try:
                job = db.query(BackfillJob).get(job_id)
                if not job:
                    return {"error": f"Job not found: {job_id}"}

                report["job"] = {
                    "id": job.id,
                    "agency_id": job.agency_id,
                    "start_date": str(job.start_date),
                    "end_date": str(job.end_date),
                    "status": job.status.value,
                    "fetched_count": job.fetched_count,
                    "new_count": job.new_count,
                    "updated_count": job.updated_count,
                    "error_count": job.error_count,
                }

                # ジョブ関連レコードの品質
                bids = db.query(Bid).filter(
                    Bid.created_at >= job.start_date,
                    Bid.created_at <= job.end_date,
                ).all()

                report["records"] = len(bids)
                report["missing_fields"] = {}
                for field in ["budget_amount", "announcement_date", "organization_name", "deadline"]:
                    count = sum(1 for b in bids if getattr(b, field) is None)
                    report["missing_fields"][field] = count

            finally:
                db.close()
        else:
            # 全体レポート
            report["overall"] = self.check_integrity()

        return report


# エイリアス（互換性のため）
BackfillDedup = BackfillDedupService