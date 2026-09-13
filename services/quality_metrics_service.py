"""品質メトリクスサービス

- 欠落フィールド、重複、取得遅延、カバレッジ率、日々の変化量を取得するユーティリティクラス
- メトリクスは `database.models.quality_metric` に保存され、`quality_alert_service` が評価します
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from database.models import Bid, AgencyInventory, Prefecture, CrawlLog
import logging

# 必須フィールドリスト - 将来的に設定ファイルから読み込む
REQUIRED_FIELDS = [
    "budget",
    "deadline",
    "prefecture_code",
    "organization_name",
    "announcement_date",
    "qualifications",
    "deliverables",
]

logger = logging.getLogger(__name__)


class QualityMetricsService:
    def __init__(self, session: Session, date_start: datetime | None = None, date_end: datetime | None = None):
        self.session = session
        self.date_start = date_start
        self.date_end = date_end

    # 将来的にプライベートメソッドとして残す
    def _bid_query(self):
        """日付範囲フィルタを適用した Bid クエリを返す"""
        query = self.session.query(Bid)
        if self.date_start:
            query = query.filter(Bid.created_at >= self.date_start)
        if self.date_end:
            query = query.filter(Bid.created_at <= self.date_end)
        return query

    def _filtered_bid_query(self, additional_filters=None):
        """日付範囲フィルタと追加のフィルタを適用した Bid クエリを返す
        
        Args:
            additional_filters: 追加のフィルタ条件のリスト（例: [Bid.field == value, ...]）
        
        Returns:
            フィルタ適用済みのクエリオブジェクト
        """
        query = self._bid_query()
        if additional_filters:
            for filter_condition in additional_filters:
                query = query.filter(filter_condition)
        return query

    def count_missing_fields(self) -> dict:
        """必須フィールドが欠落している入札件数をカウントして返す。
        例: {'project_name': 12, 'budget': 8, 'deadline': 5}
        """
        try:
            total = self._filtered_bid_query().count()
            if total == 0:
                return {}
            missing = {}
            # 各フィールドの欠損をチェック
            for field in REQUIRED_FIELDS:
                # Bid モデルにフィールドが存在するかチェック
                if hasattr(Bid, field):
                    # NULL 値の件数を取得
                    cnt = self._filtered_bid_query().filter(getattr(Bid, field) == None).count()
                    # 欠損がある場合のみ結果に追加
                    if cnt:
                        # フィールド名をキーとして欠損件数を格納
                        missing[field] = cnt
            return missing
        except Exception as e:
            logger.error(f"Error in count_missing_fields: {e}")
            return {}

    def missing_field_rate(self) -> float:
        """必須フィールドの欠損率（平均）をパーセントで返す (0.0-100.0)"""
        try:
            total = self._filtered_bid_query().count()
            if total == 0:
                return 0.0
            missing_counts = self.count_missing_fields()
            if not missing_counts:
                return 0.0
            # すべてのフィールドの欠損合計を計算
            total_missing = sum(missing_counts.values())
            # フィールドあたりの平均欠損数を計算
            avg_missing_per_field = total_missing / len(REQUIRED_FIELDS)
            # パーセンテージに変換して小数点2位で丸め
            return round((avg_missing_per_field / total) * 100, 2)
        except Exception as e:
            logger.error(f"Error in missing_field_rate: {e}")
            return 0.0

    def count_duplicates(self) -> int:
        """source_url が重複している入札件数を返す"""
        try:
            # source_urlでグループ化し、2件以上のレコードを抽出
            dup_sub = self._filtered_bid_query().with_entities(Bid.source_url).group_by(Bid.source_url).having(
                # 重複条件: 同じsource_urlが2件以上
                func.count(Bid.id) > 1
            ).subquery()
            # 重複しているsource_urlを持つレコードをカウント
            dup_count = self._filtered_bid_query().filter(Bid.source_url.in_(self.session.query(dup_sub.c.source_url))).count()
            return dup_count
        except Exception as e:
            logger.error(f"Error in count_duplicates: {e}")
            return 0

    def duplicate_rate(self) -> float:
        """重複率をパーセントで返す (0.0-100.0)"""
        try:
            total = self._filtered_bid_query().count()
            if total == 0:
                return 0.0
            dup_count = self.count_duplicates()
            # 重複率をパーセンテージで計算し、小数点2位で丸め
            return round((dup_count / total) * 100, 2)
        except Exception as e:
            logger.error(f"Error in duplicate_rate: {e}")
            return 0.0

    # TODO: この関数は後でSQL最適化する
    def acquisition_delay_median(self) -> float:
        """公開日(announcement_date) から DB登録日(created_at) までの遅延中央値（分）を返す

        全件メモリロードを避けるため、COUNT + LIMIT/OFFSET の2段クエリで中央値を計算する。
        SQLite は PERCENTILE_CONT をサポートしないため、ソート済み結果の中央要素を
        LIMIT/OFFSET で取得する。
        """
        try:
            delay_expr = (func.julianday(Bid.created_at) - func.julianday(Bid.announcement_date)) * 24 * 60

            base_query = self._filtered_bid_query([
                Bid.announcement_date != None,
                Bid.created_at != None,
                delay_expr >= 0,
            ])
            total = base_query.count()
            if total == 0:
                return 0.0

            ordered = base_query.order_by(delay_expr)

            if total % 2 == 1:
                mid = total // 2
                delay = ordered.with_entities(delay_expr).limit(1).offset(mid).scalar()
                return round(float(delay), 2) if delay is not None else 0.0

            mid = total // 2
            delays = ordered.with_entities(delay_expr).limit(2).offset(mid - 1).all()
            if not delays:
                return 0.0
            vals = [float(d) for d in delays if d is not None]
            if not vals:
                return 0.0
            if len(vals) == 1:
                return round(vals[0], 2)
            return round((vals[0] + vals[1]) / 2, 2)
        except Exception as e:
            logger.error(f"Error in acquisition_delay_median: {e}")
            return 0.0

    # TODO: この関数は後でSQL最適化する
    def coverage_rate(self) -> float:
        """インベントリに対するクロール済件数の比率 (0.0-100.0)"""
        try:
            total = self.session.query(AgencyInventory).count()
            if total == 0:
                return 0.0
            crawled = self.session.query(AgencyInventory).filter(AgencyInventory.is_crawled == True).count()
            return round((crawled / total) * 100, 2)
        except Exception as e:
            logger.error(f"Error in coverage_rate: {e}")
            return 0.0

    # TODO: この関数は後でSQL最適化する
    def coverage_municipality_rate(self) -> float:
        """対象自治体数に対する、入札データを持つ自治体数の比率 (0.0-100.0)"""
        try:
            total_prefs = self.session.query(Prefecture).count()
            if total_prefs == 0:
                return 0.0
            covered_prefs = self._filtered_bid_query([Bid.prefecture_code != None]).with_entities(Bid.prefecture_code).distinct().count()
            return round((covered_prefs / total_prefs) * 100, 2)
        except Exception as e:
            logger.error(f"Error in coverage_municipality_rate: {e}")
            return 0.0

    # TODO: この関数は後でSQL最適化する
    def daily_delta(self, days: int = 1) -> dict:
        """過去 `days` 日間の新規・更新件数変化を返す。"""
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            new_cnt = self._filtered_bid_query([Bid.created_at >= cutoff]).count()
            updated_cnt = self._filtered_bid_query([Bid.updated_at >= cutoff, Bid.updated_at != Bid.created_at]).count()
            return {"new": new_cnt, "updated": updated_cnt}
        except Exception as e:
            logger.error(f"Error in daily_delta: {e}")
            return {"new": 0, "updated": 0}

    def geps_crawler_success_rate(
        self,
        successful_runs: int | None = None,
        total_runs: int | None = None,
    ) -> float:
        """GEPS クロール成功率をパーセントで返す。"""
        try:
            # total_runsが提供されていない場合はDBから取得
            if total_runs is None:
                # CrawlLogテーブルからクエリー作成
                query = self.session.query(CrawlLog)
                # 全実行回数を取得
                total_runs = query.count()
                # 成功した実行回数を取得
                if successful_runs is None:
                    try:
                        successful_runs = query.filter(CrawlLog.status.in_(["success", "completed", "ok"])).count()
                    except Exception:
                        total_runs = 0
            if not total_runs:
                # 総実行数が0の場合はゼロを返す
                return 0.0
            if successful_runs is None:
                # 成功回数が提供されていない場合は0とする
                successful_runs = 0
            return round((successful_runs / total_runs) * 100, 2)
        except Exception as e:
            logger.error(f"Error in geps_crawler_success_rate: {e}")
            return 0.0

    def geps_selector_match_rate(
        self,
        matched_selectors: int | None = None,
        total_selectors: int | None = None,
    ) -> float:
        """GEPS セレクタマッチ率をパーセントで返す。"""
        try:
            # セレクタ総数が0または未設定の場合はゼロを返す
            if total_selectors is None or total_selectors == 0:
                return 0.0
            # マッチ数が提供されていない場合は0とする
            if matched_selectors is None:
                matched_selectors = 0
            # マッチ率をパーセンテージで計算し、小数点2位で丸め
            return round((matched_selectors / total_selectors) * 100, 2)
        except Exception as e:
            logger.error(f"Error in geps_selector_match_rate: {e}")
            return 0.0

    def collect_all_metrics(self) -> dict:
        """すべての品質メトリクスを一度に収集して dict で返す。"""
        try:
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
        except Exception as e:
            logger.error(f"Error in collect_all_metrics: {e}")
            return {}