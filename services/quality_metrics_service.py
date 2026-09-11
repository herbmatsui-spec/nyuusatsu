"""品質メトリクスサービス

- 欠落フィールド、重複、取得遅延、カバレッジ率、日々の変化量を取得するユーティリティクラス
- メトリクスは `database.models.quality_metric` に保存され、`quality_alert_service` が評価します
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from database.models import Bid, AgencyInventory, Prefecture, CrawlLog

REQUIRED_FIELDS = [
    "budget",
    "deadline",
    "prefecture_code",
    "organization_name",
    "announcement_date",
    "qualifications",
    "deliverables",
]


class QualityMetricsService:
    def __init__(self, session: Session, date_start: datetime | None = None, date_end: datetime | None = None):
        self.session = session
        self.date_start = date_start
        self.date_end = date_end

    def _bid_query(self):
        """日付範囲フィルタを適用した Bid クエリを返す"""
        query = self.session.query(Bid)
        if self.date_start:
            query = query.filter(Bid.created_at >= self.date_start)
        if self.date_end:
            query = query.filter(Bid.created_at <= self.date_end)
        return query

    def count_missing_fields(self) -> dict:
        """必須フィールドが欠落している入札件数をカウントして返す。
        例: {'project_name': 12, 'budget': 8, 'deadline': 5}
        """
        total = self._bid_query().count()
        if total == 0:
            return {}
        missing = {}
        for field in REQUIRED_FIELDS:
            if hasattr(Bid, field):
                cnt = self._bid_query().filter(getattr(Bid, field) == None).count()
                if cnt:
                    missing[field] = cnt
        return missing

    def missing_field_rate(self) -> float:
        """必須フィールドの欠損率（平均）をパーセントで返す (0.0-100.0)"""
        total = self._bid_query().count()
        if total == 0:
            return 0.0
        missing_counts = self.count_missing_fields()
        if not missing_counts:
            return 0.0
        total_missing = sum(missing_counts.values())
        avg_missing_per_field = total_missing / len(REQUIRED_FIELDS)
        return round((avg_missing_per_field / total) * 100, 2)

    def count_duplicates(self) -> int:
        """bid_number が重複している件数を返す"""
        dup_sub = self._bid_query().with_entities(Bid.source_url).group_by(Bid.source_url).having(
            func.count(Bid.id) > 1
        ).subquery()
        dup_count = self._bid_query().filter(Bid.source_url.in_(self.session.query(dup_sub.c.source_url))).count()
        return dup_count

    def duplicate_rate(self) -> float:
        """重複率をパーセントで返す (0.0-100.0)"""
        total = self._bid_query().count()
        if total == 0:
            return 0.0
        dup_count = self.count_duplicates()
        return round((dup_count / total) * 100, 2)

    def acquisition_delay_median(self) -> float:
        """公開日(announcement_date) から DB登録日(created_at) までの遅延中央値（分）を返す"""
        query = self._bid_query().filter(
            and_(Bid.announcement_date != None, Bid.created_at != None)
        )
        bids = query.all()
        if not bids:
            return 0.0
        delays = []
        for bid in bids:
            if bid.announcement_date and bid.created_at:
                delay = (bid.created_at - bid.announcement_date).total_seconds() / 60
                if delay >= 0:
                    delays.append(delay)
        if not delays:
            return 0.0
        delays.sort()
        mid = len(delays) // 2
        if len(delays) % 2 == 0:
            return round((delays[mid - 1] + delays[mid]) / 2, 2)
        return round(delays[mid], 2)

    def coverage_rate(self) -> float:
        """インベントリに対するクロール済件数の比率 (0.0-100.0)"""
        total = self.session.query(AgencyInventory).count()
        if total == 0:
            return 0.0
        crawled = self.session.query(AgencyInventory).filter(AgencyInventory.is_crawled == True).count()
        return round((crawled / total) * 100, 2)

    def coverage_municipality_rate(self) -> float:
        """対象自治体数に対する、入札データを持つ自治体数の比率 (0.0-100.0)"""
        total_prefs = self.session.query(Prefecture).count()
        if total_prefs == 0:
            return 0.0
        covered_prefs = self._bid_query().filter(Bid.prefecture_code != None).with_entities(Bid.prefecture_code).distinct().count()
        return round((covered_prefs / total_prefs) * 100, 2)

    def daily_delta(self, days: int = 1) -> dict:
        """過去 `days` 日間の新規・更新件数変化を返す。"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        new_cnt = self._bid_query().filter(Bid.created_at >= cutoff).count()
        updated_cnt = self._bid_query().filter(Bid.updated_at >= cutoff, Bid.updated_at != Bid.created_at).count()
        return {"new": new_cnt, "updated": updated_cnt}

    def geps_crawler_success_rate(
        self,
        successful_runs: int | None = None,
        total_runs: int | None = None,
    ) -> float:
        """GEPS クロール成功率をパーセントで返す。"""
        if total_runs is None:
            try:
                query = self.session.query(CrawlLog)
                total_runs = query.count()
                if successful_runs is None:
                    successful_runs = query.filter(CrawlLog.status.in_(["success", "completed", "ok"])).count()
            except Exception:
                total_runs = 0
        if not total_runs:
            return 0.0
        if successful_runs is None:
            successful_runs = 0
        return round((successful_runs / total_runs) * 100, 2)

    def geps_selector_match_rate(
        self,
        matched_selectors: int | None = None,
        total_selectors: int | None = None,
    ) -> float:
        """GEPS セレクタマッチ率をパーセントで返す。"""
        if total_selectors is None or total_selectors == 0:
            return 0.0
        if matched_selectors is None:
            matched_selectors = 0
        return round((matched_selectors / total_selectors) * 100, 2)

    def collect_all_metrics(self) -> dict:
        """すべての品質メトリクスを一度に収集して dict で返す。"""
        return {
            "missing_field_rate": self.missing_field_rate(),
            "duplicate_rate": self.duplicate_rate(),
            "acquisition_delay_median": self.acquisition_delay_median(),
            "coverage_rate": self.coverage_rate(),
            "coverage_municipality_rate": self.coverage_municipality_rate(),
            "geps_crawler_success_rate": self.geps_crawler_success_rate(),
            "geps_selector_match_rate": self.geps_selector_match_rate(),
            **{f"missing_{k}": v for k, v in self.count_missing_fields().items()},
            "duplicate_count": self.count_duplicates(),
            **{f"daily_{k}": v for k, v in self.daily_delta(days=1).items()},
        }