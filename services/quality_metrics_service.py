"""品質メトリクスサービス

- 欠落フィールド、重複、取得遅延、カバレッジ率、日々の変化量を取得するユーティリティクラス
- メトリクスは `database.models.quality_metric` に保存され、`quality_alert_service` が評価します
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from database.models import Bid, AgencyInventory, Prefecture, CrawlLog
import logging
import os

# Optional imports for memory monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

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

# LLM抽出フィールドの構造化カラムと不自然値のしきい値
LLM_EXTRACTED_FIELDS = ["budget_amount", "qualifications", "delivery_deadline", "deliverables"]
LLM_BUDGET_MAX_PLAUSIBLE = 1_000_000_000_000  # 1000億円を超える予算は抽出誤りとみなす

logger = logging.getLogger(__name__)

# Configurable parallel workers (default: CPU count)
MAX_WORKERS = int(os.getenv("QUALITY_METRICS_WORKERS", str(os.cpu_count() or 4)))

# Memory threshold for warnings (MB)
MEMORY_WARNING_THRESHOLD_MB = int(os.getenv("QUALITY_METRICS_MEMORY_WARNING_MB", "500"))


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

    def _get_memory_usage_mb(self) -> float:
        """現在のメモリ使用量を MB 単位で返す。psutil がない場合は 0.0。"""
        if not HAS_PSUTIL:
            logger.debug("psutil not available, memory monitoring disabled")
            return 0.0
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)
        except Exception as e:
            logger.debug(f"Failed to get memory usage: {e}")
            return 0.0

    def _check_memory_warning(self, context: str = "") -> None:
        """メモリ使用量が閾値を超えた場合に警告ログを出力。"""
        mem_mb = self._get_memory_usage_mb()
        if mem_mb > MEMORY_WARNING_THRESHOLD_MB:
            logger.warning(
                f"High memory usage detected {context}: {mem_mb:.1f} MB "
                f"(threshold: {MEMORY_WARNING_THRESHOLD_MB} MB)"
            )
        elif mem_mb > 0:
            logger.debug(f"Memory usage {context}: {mem_mb:.1f} MB")

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
    def acquisition_delay_median(self, chunk_size: int = 10000) -> float:
        """公開日(announcement_date) から DB登録日(created_at) までの遅延中央値（分）を返す

        全件メモリロードを避けるため、COUNT + LIMIT/OFFSET の2段クエリで中央値を計算する。
        SQLite は PERCENTILE_CONT をサポートしないため、ソート済み結果の中央要素を
        LIMIT/OFFSET で取得する。

        大量データ（chunk_size 以上）の場合、チャンク単位で処理してメモリ使用量を抑制。

        Args:
            chunk_size: チャンク処理の閾値。この件数を超える場合は分割処理を行う。
        """
        try:
            self._check_memory_warning("before acquisition_delay_median")
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

            if total <= chunk_size:
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

            return self._compute_median_chunked(base_query, delay_expr, total, chunk_size)
        except Exception as e:
            logger.error(f"Error in acquisition_delay_median: {e}")
            return 0.0
        finally:
            self._check_memory_warning("after acquisition_delay_median")

    def _compute_median_chunked(self, base_query, delay_expr, total: int, chunk_size: int) -> float:
        """大規模データ用のチャンク分割中央値計算。

        SQLite では PERCENTILE_CONT が使えないため、中央値の近似値を
        複数チャンクからサンプリングして計算する。
        """
        # Sample at regular intervals to estimate median
        sample_indices = []
        num_samples = min(1000, total)  # Max 1000 samples
        step = max(1, total // num_samples)

        for i in range(0, total, step):
            sample_indices.append(i)
            if len(sample_indices) >= num_samples:
                break

        # Ensure we include the exact middle
        mid = total // 2
        if mid not in sample_indices:
            sample_indices.append(mid)
        if total % 2 == 0 and (mid - 1) not in sample_indices:
            sample_indices.append(mid - 1)

        sample_indices = sorted(set(sample_indices))

        # Fetch sampled values
        ordered = base_query.order_by(delay_expr)
        sampled_values = []

        for idx in sample_indices:
            delay = ordered.with_entities(delay_expr).limit(1).offset(idx).scalar()
            if delay is not None:
                sampled_values.append(float(delay))

        if not sampled_values:
            return 0.0

        # Sort and find median of samples
        sampled_values.sort()
        n = len(sampled_values)
        if n % 2 == 1:
            return round(sampled_values[n // 2], 2)
        return round((sampled_values[n // 2 - 1] + sampled_values[n // 2]) / 2, 2)

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

    def collect_llm_extraction_quality(self) -> dict:
        """LLM抽出フィールドの品質メトリクスを収集する。

        構造化カラム（budget_amount / qualifications / delivery_deadline / deliverables）
        の欠損率と、予算額の不自然値（0以下・極端に大きい値）の件数・率を返す。
        """
        try:
            total = self._bid_query().count()
            metrics: dict = {"llm_sample_count": float(total)}
            if total == 0:
                for field in LLM_EXTRACTED_FIELDS:
                    metrics[f"llm_missing_{field}_rate"] = 0.0
                metrics["llm_budget_anomaly_rate"] = 0.0
                metrics["llm_budget_anomaly_count"] = 0.0
                return metrics
            for field in LLM_EXTRACTED_FIELDS:
                column = getattr(Bid, field, None)
                if column is None:
                    continue
                missing = self._filtered_bid_query([
                    column.is_(None) | (func.trim(column) == "") if field != "budget_amount" else column.is_(None)
                ]).count()
                metrics[f"llm_missing_{field}_rate"] = round(missing / total * 100, 2)
            anomaly = self._filtered_bid_query([
                Bid.budget_amount.isnot(None),
                (Bid.budget_amount <= 0) | (Bid.budget_amount >= LLM_BUDGET_MAX_PLAUSIBLE),
            ]).count()
            metrics["llm_budget_anomaly_count"] = float(anomaly)
            metrics["llm_budget_anomaly_rate"] = round(anomaly / total * 100, 2)
            return metrics
        except Exception as e:
            logger.error(f"Error in collect_llm_extraction_quality: {e}")
            return {"llm_sample_count": 0.0}

    def collect_all_metrics(self, parallel: bool = False) -> dict:
        """すべての品質メトリクスを一度に収集して dict で返す。

        Args:
            parallel: True の場合、ThreadPoolExecutor で独立したメトリクスを並列収集
        """
        try:
            if parallel:
                return self._collect_all_metrics_parallel()
            return self._collect_all_metrics_sequential()
        except Exception as e:
            logger.error(f"Error in collect_all_metrics: {e}")
            return {}

    def _collect_all_metrics_sequential(self) -> dict:
        """逐次実行で全メトリクスを収集（従来通り）。"""
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
            **self.collect_llm_extraction_quality(),
        }

    def _collect_all_metrics_parallel(self) -> dict:
        """並列実行で全メトリクスを収集（大規模データ向け）。

        注意: DB接続はスレッドセーフでないため、各タスクは独立したセッションを使用する必要があります。
        この実装では同一セッション内で読み取り専用クエリを並列実行します。
        SQLite では並列読み取りが制限されるため、PostgreSQL 等での使用を推奨します。
        """
        metrics = {}

        # 独立して実行可能なメトリクス関数のマッピング
        metric_functions = {
            "missing_field_rate": self.missing_field_rate,
            "duplicate_rate": self.duplicate_rate,
            "acquisition_delay_median": self.acquisition_delay_median,
            "coverage_rate": self.coverage_rate,
            "coverage_municipality_rate": self.coverage_municipality_rate,
            "geps_crawler_success_rate": self.geps_crawler_success_rate,
            "geps_selector_match_rate": self.geps_selector_match_rate,
            "duplicate_count": self.count_duplicates,
        }

        # count_missing_fields と daily_delta は後で個別追加
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(metric_functions))) as executor:
            future_to_name = {
                executor.submit(fn): name
                for name, fn in metric_functions.items()
            }

            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    metrics[name] = future.result()
                except Exception as e:
                    logger.error(f"Error collecting {name} in parallel: {e}", exc_info=True)
                    metrics[name] = 0.0

        # 残りのメトリクスを逐次実行（count_missing_fields は並列化しにくいため）
        try:
            missing_fields = self.count_missing_fields()
            metrics.update({f"missing_{k}": v for k, v in missing_fields.items()})
        except Exception as e:
            logger.error(f"Error collecting missing fields: {e}", exc_info=True)

        try:
            daily = self.daily_delta(days=1)
            metrics.update({f"daily_{k}": v for k, v in daily.items()})
        except Exception as e:
            logger.error(f"Error collecting daily delta: {e}", exc_info=True)

        try:
            metrics.update(self.collect_llm_extraction_quality())
        except Exception as e:
            logger.error(f"Error collecting llm extraction quality: {e}", exc_info=True)

        return metrics
