"""品質メトリクスサービス

- 欠落フィールド、重複、取得遅延、カバレッジ率、日々の変化量を取得するユーティリティクラス
- メトリクスは `database.models.quality_metric` に保存され、`quality_alert_service` が評価します
- リポジトリパターンを使用してDBアクセスを抽象化（Step 5）
- 型ヒント付き（Step 6）
- SQL最適化済み（Step 8）
- キャッシング機能付き（Step 14）
"""

from typing import Optional, Dict, Any, List
from functools import lru_cache
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from database.models import Bid, AgencyInventory, Prefecture, CrawlLog
from database.repositories import BidRepository
import logging
import os

# Optional imports for memory monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from memory_profiler import profile
    HAS_MEMORY_PROFILER = True
except ImportError:
    HAS_MEMORY_PROFILER = False
    def profile(func):
        return func

logger = logging.getLogger(__name__)

# Configurable parallel workers (default: CPU count)
MAX_WORKERS = int(os.getenv("QUALITY_METRICS_WORKERS", str(os.cpu_count() or 4)))

# Memory threshold for warnings (MB)
MEMORY_WARNING_THRESHOLD_MB = int(os.getenv("QUALITY_METRICS_MEMORY_WARNING_MB", "500"))

logger = logging.getLogger(__name__)


REQUIRED_FIELDS: List[str] = [
    "budget",
    "deadline",
    "prefecture_code",
    "organization_name",
    "announcement_date",
    "qualifications",
    "deliverables",
]


class QualityMetricsService:
    """品質メトリクスを収集・計算するサービス。

    Args:
        session: SQLAlchemy Session
        date_start: 分析開始日（オプション）
        date_end: 分析終了日（オプション）
        use_cache: キャッシングを有効にするか（デフォルト True）
    """

    def __init__(
        self,
        session: Session,
        date_start: Optional[datetime] = None,
        date_end: Optional[datetime] = None,
        use_cache: bool = True,
    ):
        self.session: Session = session
        self.date_start: Optional[datetime] = date_start
        self.date_end: Optional[datetime] = date_end
        self.use_cache: bool = use_cache
        self._bid_repo: BidRepository = BidRepository(session)

    def _clear_cache(self) -> None:
        """キャッシングをクリアする。データ変更後や日付範囲変更後に呼ぶ。"""
        self.count_missing_fields.cache_clear()
        self.count_duplicates.cache_clear()
        self.acquisition_delay_median.cache_clear()

    def _get_memory_usage_mb(self) -> float:
        """現在のメモリ使用量を MB 単位で返す。psutil がない場合は 0.0。"""
        if not HAS_PSUTIL:
            return 0.0
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)
        except Exception:
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

    def _bid_query(self):
        """日付範囲フィルタを適用した Bid クエリを返す"""
        query = self.session.query(Bid)
        if self.date_start:
            query = query.filter(Bid.created_at >= self.date_start)
        if self.date_end:
            query = query.filter(Bid.created_at <= self.date_end)
        return query

    def _filtered_bid_query(self, additional_filters: Optional[list] = None):
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

    @lru_cache(maxsize=1)
    def count_missing_fields(self) -> Dict[str, int]:
        """必須フィールドが欠落している入朑件数をカウントして返す。

        例: {'budget': 12, 'deadline': 8, 'organization_name': 5}

        Returns:
            フィールド名をキー、欠損件数を値とする辞書。欠損0のフィールドは含めない。
        """
        try:
            base_query = self._filtered_bid_query()
            total = base_query.count()
            if total == 0:
                return {}

            missing: Dict[str, int] = {}
            # Step 8 最適化: CASE式で1クエリに集約
            case_exprs: Dict[str, Any] = {}
            for field in REQUIRED_FIELDS:
                if hasattr(Bid, field):
                    case_exprs[field] = case(
                        (getattr(Bid, field).is_(None), 1), else_=0
                    )

            if case_exprs:
                col_exprs = list(case_exprs.values())
                sums = base_query.with_entities(
                    *[func.sum(ce) for ce in col_exprs]
                ).one()

            for i, field in enumerate(case_exprs.keys()):
                cnt = int(sums[i]) if sums[i] is not None else 0
                if cnt > 0:
                    missing[field] = cnt

            return missing
        except Exception as e:
            logger.error(f"Error in count_missing_fields: {e}")
            return {}

    def missing_field_rate(self) -> float:
        """必須フィールドの欠失率（平均）をパーセントで返す (0.0-100.0)

        Returns:
            欠失率パーセント（小数点2位）
        """
        try:
            total = self._filtered_bid_query().count()
            if total == 0:
                return 0.0
            missing_counts = self.count_missing_fields()
            if not missing_counts:
                return 0.0
            total_missing = sum(missing_counts.values())
            avg_missing_per_field = total_missing / len(REQUIRED_FIELDS)
            return round((avg_missing_per_field / total) * 100, 2)
        except Exception as e:
            logger.error(f"Error in missing_field_rate: {e}")
            return 0.0

    def count_duplicates(self) -> int:
        """source_url が重複している入札件数を返す

        Returns:
            重複件数
        """
        try:
            dup_sub = self._filtered_bid_query().with_entities(Bid.source_url).group_by(Bid.source_url).having(
                func.count(Bid.id) > 1
            ).subquery()
            dup_count = self._filtered_bid_query().filter(
                Bid.source_url.in_(self.session.query(dup_sub.c.source_url))
            ).count()
            return dup_count
        except Exception as e:
            logger.error(f"Error in count_duplicates: {e}")
            return 0

    def duplicate_rate(self) -> float:
        """重複率をパーセントで返す (0.0-100.0)

        Returns:
            重複率パーセント（小数点2位）
        """
        try:
            total = self._filtered_bid_query().count()
            if total == 0:
                return 0.0
            dup_count = self.count_duplicates()
            return round((dup_count / total) * 100, 2)
        except Exception as e:
            logger.error(f"Error in duplicate_rate: {e}")
            return 0.0

    def acquisition_delay_median(self, chunk_size: int = 10000) -> float:
        """公開日(announcement_date) から DB登録日(created_at) までの遅延中央値（分）を返す

        LIMIT/OFFSET の2段クエリで中央値を計算する。SQLite は PERCENTILE_CONT を
        サポートしないため、ソート済み結果の中央要素を LIMIT/OFFSET で取得する。

        大量データ（chunk_size 以上）の場合、チャンク単位で処理してメモリ使用量を抑制。

        Args:
            chunk_size: チャンク処理の閾値。この件数を超える場合は分割処理を行う。

        Returns:
            遅延中央値（分）
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

            # For small datasets, use simple approach
            if total <= chunk_size:
                return self._compute_median_simple(base_query, delay_expr, total)

            # For large datasets, use chunked approach to avoid memory issues
            logger.info(f"Large dataset ({total} records), using chunked median computation")
            return self._compute_median_chunked(base_query, delay_expr, total, chunk_size)
        except Exception as e:
            logger.error(f"Error in acquisition_delay_median: {e}")
            return 0.0
        finally:
            self._check_memory_warning("after acquisition_delay_median")

    def _compute_median_simple(self, base_query, delay_expr, total: int) -> float:
        """小規模データ用のシンプルな中央値計算。"""
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
        else:
            return round((sampled_values[n // 2 - 1] + sampled_values[n // 2]) / 2, 2)

    def coverage_rate(self) -> float:
        """インベントリに対するクロール済件数の比率 (0.0-100.0)

        Returns:
            カバレッジ率パーセント（小数点2位）
        """
        try:
            total = self.session.query(AgencyInventory).count()
            if total == 0:
                return 0.0
            crawled = self.session.query(AgencyInventory).filter(
                AgencyInventory.is_crawled == True
            ).count()
            return round((crawled / total) * 100, 2)
        except Exception as e:
            logger.error(f"Error in coverage_rate: {e}")
            return 0.0

    def coverage_municipality_rate(self) -> float:
        """対象自治体数に対する、入札データを持つ自治体数の比率 (0.0-100.0)

        Returns:
            自治体カバレッジ率パーセント（小数点2位）
        """
        try:
            total_prefs = self.session.query(Prefecture).count()
            if total_prefs == 0:
                return 0.0
            covered_prefs = self._filtered_bid_query([
                Bid.prefecture_code != None
            ]).with_entities(Bid.prefecture_code).distinct().count()
            return round((covered_prefs / total_prefs) * 100, 2)
        except Exception as e:
            logger.error(f"Error in coverage_municipality_rate: {e}")
            return 0.0

    def daily_delta(self, days: int = 1) -> Dict[str, int]:
        """過去 `days` 日間の新規・更新件数変化を返す。

        Args:
            days: 遡及日数

        Returns:
            {'new': 新規件数, 'updated': 更新件数}
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            new_cnt = self._filtered_bid_query([
                Bid.created_at >= cutoff
            ]).count()
            updated_cnt = self._filtered_bid_query([
                Bid.updated_at >= cutoff,
                Bid.updated_at != Bid.created_at
            ]).count()
            return {"new": new_cnt, "updated": updated_cnt}
        except Exception as e:
            logger.error(f"Error in daily_delta: {e}")
            return {"new": 0, "updated": 0}

    def geps_crawler_success_rate(
        self,
        successful_runs: Optional[int] = None,
        total_runs: Optional[int] = None,
    ) -> float:
        """GEPS クロール成功率をパーセントで返す (0.0-100.0)

        Args:
            successful_runs: 成功回数（省略時はDBから取得）
            total_runs: 総実行回数（省略時はDBから取得）

        Returns:
            成功率パーセント（小数点2位）
        """
        try:
            if total_runs is None:
                query = self.session.query(CrawlLog)
                total_runs = query.count()
                if successful_runs is None:
                    try:
                        successful_runs = query.filter(
                            CrawlLog.status.in_(["success", "completed", "ok"])
                        ).count()
                    except Exception:
                        total_runs = 0
            if not total_runs:
                return 0.0
            if successful_runs is None:
                successful_runs = 0
            return round((successful_runs / total_runs) * 100, 2)
        except Exception as e:
            logger.error(f"Error in geps_crawler_success_rate: {e}")
            return 0.0

    def geps_selector_match_rate(
        self,
        matched_selectors: Optional[int] = None,
        total_selectors: Optional[int] = None,
    ) -> float:
        """GEPS セレクタマッチ率をパーセントで返す (0.0-100.0)

        Args:
            matched_selectors: マッチしたセレクタ数
            total_selectors: 総セレクタ数

        Returns:
            マッチ率パーセント（小数点2位）
        """
        try:
            if total_selectors is None or total_selectors == 0:
                return 0.0
            if matched_selectors is None:
                matched_selectors = 0
            return round((matched_selectors / total_selectors) * 100, 2)
        except Exception as e:
            logger.error(f"Error in geps_selector_match_rate: {e}")
            return 0.0

    def collect_all_metrics(self, parallel: bool = False) -> Dict[str, Any]:
        """すべての品質メトリクスを一度に収集して dict で返す。

        Args:
            parallel: True の場合、ThreadPoolExecutor で独立したメトリクスを並列収集

        Returns:
            メトリクス名をキー、値を値とする辞書
        """
        try:
            if parallel:
                return self._collect_all_metrics_parallel()
            
            return self._collect_all_metrics_sequential()
        except Exception as e:
            logger.error(f"Error in collect_all_metrics: {e}")
            return {}

    def _collect_all_metrics_sequential(self) -> Dict[str, Any]:
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
        }

    def _collect_all_metrics_parallel(self) -> Dict[str, Any]:
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
                executor.submit(func): name 
                for name, func in metric_functions.items()
            }
            
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    metrics[name] = future.result()
                except Exception as e:
                    logger.error(f"Error collecting {name} in parallel: {e}")
                    metrics[name] = 0.0
        
        # 残りのメトリクスを逐次実行（count_missing_fields は並列化しにくいため）
        try:
            missing_fields = self.count_missing_fields()
            metrics.update({f"missing_{k}": v for k, v in missing_fields.items()})
        except Exception as e:
            logger.error(f"Error collecting missing fields: {e}")
        
        try:
            daily = self.daily_delta(days=1)
            metrics.update({f"daily_{k}": v for k, v in daily.items()})
        except Exception as e:
            logger.error(f"Error collecting daily delta: {e}")
        
        return metrics
