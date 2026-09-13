# 実装計画書: コードレビュー Critical/High 修正

**ベース**: `plans/CODE_REVIEW.md` (2026-09-11)  
**目的**: Critical 6件 + High 6件 + Medium 3件のバグを段階的に修正  
**実装順序**: Critical → High → Medium → Final Verification

---

## Phase 1: Critical (即日対応)

### Step 1: scheduler.py モジュールレベル logger 追加 [C1]
- **対象**: `scheduler.py`
- **問題**: `_run_forecast_crawl_async`, `_run_morning_digest_async`, `_run_backfill_async`, `_run_award_crawl_async` が裸の `logger` を使用
- **修正**: モジュールレベルに `logger = logging.getLogger(__name__)` を追加
- **検証**: `python -c "import scheduler; logger"` で NameError が解消されること

### Step 2: config_dir.py PlanConfig re-export [C2]
- **対象**: `config_dir.py`
- **問題**: `app_dashboard.py:23` が `from config_dir import AppConfig, PlanConfig` で ImportError
- **修正**: `from config import AppConfig, PlanConfig` に変更
- **検証**: `python -c "from config_dir import PlanConfig"` 成功

### Step 3: バックアップファイル削除 + .gitignore 更新 [C5, C6]
- **対象**: 17 ファイルの `.bak`/`.bak2`/`.backup` + `.coverage`, `bids_system.db`
- **修正**: Git から削除 + `.gitignore` に `*.bak`, `*.bak2`, `*.backup` を追加
- **検証**: `git status` でクリーン

### Step 4: test_count_duplicates no-op 修正 [C4]
- **対象**: `tests/unit/test_quality_metrics_service.py`
- **問題**: `test_count_duplicates` が自身をモック、`test_count_duplicates_uses_bid_number` が misleading
- **修正**: `count_duplicates()` を実際にテストする — MagicMock でクエリチェーンを設定し、`source_url` グルーピング SQL が呼ばれることを検証
- **検証**: `pytest tests/unit/test_quality_metrics_service.py -k "duplicate" -v` パス

### Step 5: pytest.ini カバレッジパス修正 [H7]
- **対象**: `pytest.ini`
- **修正**: `--cov=geps_crawler.py` を `--cov=crawler.geps_crawler` に変更
- **検証**: `python -m pytest --co` でエラーなし

---

## Phase 2: High (1-2週間)

### Step 6: QualityThreshold に lower_is_worse 追加 [H3]
- **対象**: `database/models/quality_threshold.py`, `scripts/seed_quality_thresholds.py`
- **修正**: `lower_is_worse` Boolean カラム追加 + seed で保存
- **検証**: モデルインポート + seed スクリプト実行

### Step 7: QualityMetric に period_start/period_end 追加 [H4]
- **対象**: `database/models/quality_metric.py`, `scripts/collect_quality_metrics.py`
- **修正**: カラム追加 + 収集時に期間記録
- **検証**: collect_metrics スクリプト --date-range で動作確認

### Step 8: acquisition_delay_median() SQL最適化 [H2]
- **対象**: `services/quality_metrics_service.py`
- **修正**: `.all()` → `.count()` + `LIMIT/OFFSET` 分割ソート (SQLite 互換)
- **検証**: 既存テストパス + 大量データでのメモリプロファイル

### Step 9: BaseCrawler.extract_item_date を abstractmethod 化 [H5]
- **対象**: `crawler/base_crawler.py`
- **修正**: `@abstractmethod` 追加、`getattr` チェックを削除
- **検証**: `GEPSCrawler` が `extract_item_date` を実装していること確認

### Step 10: GEPS ヒューリスティック重複修正 [H8]
- **対象**: `crawler/geps_crawler.py`
- **問題**: `input[type="date"]` が start_date と end_date の両方のヒューリスティック候補に含まれる
- **修正**: start_date では `input[type="date"]` を除外、または position による区別
- **検証**: `test_geps_selectors.py` で `_find_date_field("end_date")` が異なる要素を返すこと

---

## Phase 3: Medium (技術的負債)

### Step 11: health_checker.py text() 修正 [M8]
- **対象**: `services/health_checker.py:93`
- **修正**: `session.execute("SELECT 1")` → `session.execute(text("SELECT 1"))`
- **検証**: ヘルスチェック実行

---

## Phase 4: Final Verification

### Step 12: 全修正の最終検証
- `flake8` チェック (F821 検出確認)
- `pytest tests/ -v` 全テスト通過
- `python -c "import scheduler, config_dir, services.quality_alert_service"` インポート成功
