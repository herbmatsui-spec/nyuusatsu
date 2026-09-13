# 48ステップ実装計画書

**プロジェクト**: 入札システム (Bid Extraction System)  
**ベース**: コードレビュー (`plans/CODE_REVIEW.md`)  
**目的**: 低性能LLMでも実装可能な48ステップ計画書

---

## 概要

本計画書は、コードレビューで特定された主要問題を48の具体的なステップに分割し、段階的に実装することで、システムのアーキテクチャを強化し、保守性を向上させ、運用を安定化させることを目的としています。各ステップは独立しており、前のステップが完了した後に次のステップに進むことができます。

**主要問題**:
1. `db_manager.py` が本番DBと別系統で、トランザクション・マイグレーション管理から外れている
2. `BaseCrawler.fetch()` が同期HTTP中心で、非同期クローラと設計が分断している
3. `QualityMetricsService.acquisition_delay_median()` が全件メモリロードで、スケール時に危険
4. `QualityThreshold` にYAML側の `lower_is_worse` が反映されていない
5. GEPSセレクタがハードコード・プレースホルダ中心で、P3の堅牢化計画と未整合
6. スケジューラの例外ハンドリングが広く捕まえて継続しており、障害分類・リトライポリシーの強化が必要

---

## 48ステップ実装計画

### ステップ1-16: DB統合・品質メトリクス改善

| ステップ | タスク | 詳細 | 影響 |
|------|------|------|------|
| **1** | `db_manager.py` をSQLAlchemyモデルへ統合 | `CrawlHistory`, `CrawledUrl`, `Settings` を `database/models/` に移動し、Alembicマイグレーションを作成。`db_manager.py` をリポジトリパターンでラップし、`database/repositories/` に移行。 | DB操作の一元化、トランザクション管理の強化、マイグレーション管理の簡素化 |
| **2** | `QualityMetric` に収集期間追加 | `period_start`/`period_end` カラムを追加し、`collect_quality_metrics.py` で設定。`collect_all_metrics()` を修正し、期間を保存。 | メトリクスの期間追跡が可能になり、後分析が容易になる |
| **3** | `QualityThreshold` に `lower_is_worse` 追加 | `quality_threshold.py` に `lower_is_worse` カラムを追加し、マイグレーションを作成。`quality_alert_service.py` でYAMLとDBの `lower_is_worse` を同期。 | しきい値評価の整合性確保 |
| **4** | `acquisition_delay_median()` をSQL集計化 | SQLiteの `PERCENTILE_CONT` または近似アルゴリズムを実装。`database/repositories/bid_repository.py` に `get_delay_percentile()` メソッドを追加。 | メモリ使用量削減、件数増加時のパフォーマンス改善 |
| **5** | `quality_metrics_service.py` をリファクタリング | `count_missing_fields()`、`missing_field_rate()`、`duplicate_rate()`、`acquisition_delay_median()`、`coverage_rate()`、`coverage_municipality_rate()`、`daily_delta()`、`collect_all_metrics()` をリポジトリパターンでラップ。 | ビジネスロジックとDBアクセス層の分離、テスト容易化 |
| **6** | `quality_metrics_service.py` に型ヒント追加 | 関数シグネチャにPydanticまたは`typing`モジュールを使用して型注釈を追加。`mypy`で検証。 | 静的解析、IDE支援の強化 |
| **7** | `quality_metrics_service.py` にエラーハンドリング改善 | `try/except` を強化し、`logger.error` で詳細なログ記録。`ValueError`、`TypeError` 等を適切処理。 | デバッグ容易化、障害原因の特定容易化 |
| **8** | `quality_metrics_service.py` にパフォーマンス最適化 | `count_missing_fields()` をSQL `CASE` 式で集約、`duplicate_rate()` をウィンドウ関数で計算、`coverage_rate()` をJOINで計算。 | クエリ実行時間の短縮 |
| **9** | `quality_metrics_service.py` にドキュメント追加 | 各メソッドにdocstringを追加し、`__init__` に型ヒントを追加。`pydoc`で検証。 | コード理解の促進 |
| **10** | `quality_metrics_service.py` にユニットテスト追加 | `pytest` + `MagicMock` で各メソッドをテスト。`tests/unit/test_quality_metrics_service.py` を拡張。 | コードの信頼性向上、リファクタリング時の安全確保 |
| **11** | `quality_metrics_service.py` にベンチマーク追加 | `timeit` または `pytest-benchmark` で主要メソッドのパフォーマンスを測定。 | パフォーマンス退化を早期検出 |
| **12** | `quality_metrics_service.py` にメモリ使用量監視追加 | `memory_profiler` または `psutil` でメモリ使用量を監視し、`acquisition_delay_median()` で `LIMIT/OFFSET` 処理を実装。 | OOMエラーの防止 |
| **13** | `quality_metrics_service.py` に並列処理追加 | `concurrent.futures.ThreadPoolExecutor` で `count_missing_fields()`、`duplicate_rate()` 等を並列実行。 | 大規模データ時の処理時間短縮 |
| **14** | `quality_metrics_service.py` にキャッシュ追加 | `functools.lru_cache` で `missing_field_rate()`、`duplicate_rate()` 等をキャッシュ。 | 繰り返し呼び出し時の高速化 |
| **15** | `quality_metrics_service.py` にログレベル調整 | `logger.debug`、`logger.info`、`logger.warning`、`logger.error` を適切使用。 | ログの可読性向上、デバッグ容易化 |
| **16** | `quality_metrics_service.py` にCI/CD統合 | `pytest`、`mypy`、`black`、`isort` をGitHub Actionsで実行。 | 品質ゲート自動化 |

### ステップ17-32: クローラー・セレクタ改善

| ステップ | タスク | 詳細 | 影響 |
|------|------|------|------|
| **17** | GEPSセレクタ外部化 | `crawler/config/geps_selectors.yaml` を作成し、ページ種別ごとのセレクタマップを定義。`crawler/utils/selector_loader.py` で `_load_selectors()` を実装。`geps_crawler.py` を修正し、`selector_loader` を使用。 | セレクタの安定性向上、メンテナンス容易化、P3 Step 13-17 完了 |
| **18** | GEPSセレクタバージョニング | `crawler/config/geps_selectors.yaml` に `selectors_version: "2026.09"` キーを追加。`selector_loader.py` でバージョン管理を実装。`geps_crawler.py` で `selector_version` をログ記録。 | セレクタ変更の追跡、ロールバック可能性確保 |
| **19** | セレクタ検証ユーティリティ作成 | `crawler/utils/selector_validator.py` を作成し、HTMLとセレクタのマッチングを検証。`tests/unit/test_geps_selectors.py` でフィクスチャHTMLを使用。 | セレクタの回帰テスト、品質保証 |
| **20** | プレースホルダセレクタを実セレクタに置換 | `geps_crawler.py` の `input[placeholder*="開始"]` 等を実際のGEPSサイトHTML解析し、`id`/`class`/`name` 属性ベースのセレクタに書き換え。 | セレクタの信頼性向上、マッチ率改善 |
| **21** | フォールバックセレクタ複数指定対応 | `crawler/config/geps_selectors.yaml` で `selectors: ["#startDate", "input[name='startDate']", "input[placeholder*='開始']"]` 形式で優先順位付けを実装。`selector_loader.py` で `_get_selectors()` を実装。 | セレクタの堅牢性向上、フォールバック機能確保 |
| **22** | 日付入力フィールド自動検出ロジック追加 | `crawler/utils/date_field_detector.py` を作成し、`type="date"`、`class*="datepicker"`、`placeholder*="開始"` 等を検出。`geps_crawler.py` で `_detect_date_fields()` を実装。 | 手動セレクタ指定の削減、自動検出機能追加 |
| **23** | ページ遷移待機の明示的待機化 | `crawler/utils/wait_strategy.py` を作成し、`WebDriverWait` 相当を `requests-html` / `playwright` で実装。`geps_crawler.py` で `_wait_for_element()` を実装。 | JSレンダリング対応、安定したページ読み込み |
| **24** | 単体テスト用HTMLフィクスチャ追加 | `tests/fixtures/geps/` に `list_page.html`、`detail_page.html`、`search_form.html` を保存。`tests/unit/test_geps_selectors.py` で `pytest.fixture` を使用。 | 回帰テストの安定化、CIでの実サイトアクセス削減 |
| **25** | セレクタ回帰テスト作成 | `tests/unit/test_geps_selectors.py` を作成し、フィクスチャHTMLに対して全セレクタがマッチするか検証。`selector_validator.py` と統合。 | セレクタの品質保証、自動テスト |
| **26** | 実サイト対応統合テスト (手動実行用スクリプト) | `scripts/test_geps_live.py` を作成し、実サイトアクセス → 件数取得 → ログ出力。`geps_crawler.py` の `search_bids()` を呼び出し。 | 本番環境検証、運用監視 |
| **27** | 監視用メトリクス追加 | `services/quality_metrics_service.py` に `geps_crawler_success_rate`、`geps_selector_match_rate` を追加。`collect_quality_metrics.py` で収集。 | GEPSクローラの品質監視、アラート発火の基盤 |
| **28** | アラート閾値設定 (成功率 90% 未満で警告) | `config/quality_thresholds.yaml` に `geps_crawler_success_rate`、`geps_selector_match_rate` の閾値を追加。`quality_alert_service.py` で評価。 | GEPSクローラの異常検知、早期対応 |
| **29** | `BaseCrawler` を非同期化 | `crawler/base_crawler.py` を修正し、`async_fetch()`、`async_crawl_range()` を追加。`geps_crawler.py` を修正し、`async` 版を実装。 | クローラ基盤の統一、並列処理対応 |
| **30** | `BaseCrawler` にリトライロジック改善 | `backoff` にジッター（`random.uniform(0, 0.5)`）を追加。`max_retries`、`retry_delay` を設定可能に。`geps_crawler.py` で `retry`、`backoff` を設定。 | リトライの公平性向上、バースト防止 |
| **31** | `BaseCrawler` にレート制限追加 | `crawler/utils/rate_limiter.py` を作成し、`time.sleep()` でリクエスト間隔を制御。`geps_crawler.py` で `rate_limit` を設定。 | サーバー負荷軽減、アクセス制限回避 |
| **32** | `BaseCrawler` にプロキシサポート追加 | `crawler/utils/proxy_manager.py` を作成し、`HTTP_PROXY`、`HTTPS_PROXY` を読み込み。`geps_crawler.py` で `proxy_manager` を使用。 | ネットワーク環境対応、クロール範囲拡大 |

### ステップ33-48: スケジューラ・監視・ドキュメント改善

| ステップ | タスク | 詳細 | 影響 |
|------|------|------|------|
| **33** | スケジューラ例外分類 | `scheduler.py` を修正し、`TransientError`、`FatalError`、`ConfigurationError` 等を定義。`except` を細分化。 | 適切なリトライ、障害原因の特定容易化 |
| **34** | スケジューラ指数バックオフ | `scheduler.py` の `_run_*_async()` で `retry_after` を計算し、`time.sleep(retry_after)` を実装。 | リトライの効率化、サーバー負荷軽減 |
| **35** | スケジューラ最大リトライ | `scheduler.py` で `max_retries` を設定し、`retry_count` を追跡。`max_retries` 超過で `alert_manager` に通知。 | 無限リトライの防止、障害検知 |
| **36** | スケジューラDead Letter Queue | `scheduler.py` に `dead_letter_queue` を追加し、`max_retries` 超過のジョブを保存。`scripts/retry_failed_jobs.py` で手動再実行。 | 障害ジョブの追跡、再実行可能性 |
| **37** | スケジューラヘルスチェック改善 | `scheduler.py` の `_run_health_check()` を修正し、Redis、DB、キュー深度、スケジューラ、パイプラインの各コンポーネントを詳細チェック。 | システムヘルス監視の強化 |
| **38** | スケジューラアラート閾値調整 | `scheduler.py` の `_run_health_check()` で `alert_manager.evaluate_and_alert()` を使用し、閾値を `config/quality_thresholds.yaml` から読み込み。 | アラート精度向上、運用調整容易化 |
| **39** | スケジューラログ構造化 | `scheduler.py` の `logger.info`、`logger.error` を構造化ログ（JSON）に変更。`logging.config` で設定。 | ログ解析の容易化、SIEM連携 |
| **40** | スケジューラメトリクス収集改善 | `scheduler.py` の `_run_metrics_cleanup()` を修正し、`quality_metric` に `job_id`、`status`、`duration` を追加。 | ジョブ実行の追跡、分析容易化 |
| **41** | スケジューラ監視ダッシュボード | `app_admin.py` にスケジューラ監視タブを追加し、ジョブ状態、実行履歴、失敗率を表示。 | 運用可視化、迅速な対応 |
| **42** | スケジューラドキュメント作成 | `docs/operations/scheduler.md` を作成し、ジョブ定義、例外ハンドリング、監視方法、トラブルシューティング手順を記載。 | 運用ドキュメントの整備、引き継ぎ容易化 |
| **43** | スケジューラCI/CD統合 | `.github/workflows/scheduler.yml` を作成し、`scheduler.py` の構文チェック、ユニットテスト、ヘルスチェックを実行。 | 自動品質ゲート、障害の早期検知 |
| **44** | スケジューラセキュリティ強化 | `scheduler.py` に `auth_decorator.py` で認証を追加し、`plan_gate.py` で機能制限を実装。 | システムセキュリティの強化、アクセス制御 |
| **45** | スケジューラパフォーマンス監視 | `scheduler.py` に `metrics_collector.py` で `scheduler_job_duration`、`scheduler_job_success_rate` を記録。`app_dashboard.py` でグラフ表示。 | パフォーマンス監視、容量計画の容易化 |
| **46** | スケジューラ自動スケーリング | `scheduler.py` に `auto_scale.py` で `job_queue_size`、`cpu_usage` を監視し、`cron` でジョブ数を調整。 | リソース効率の最適化、運用負荷軽減 |
| **47** | スケジューラ障害シミュレーション | `scripts/simulate_scheduler_failure.py` を作成し、`scheduler.py` の `_run_*_async()` をランダムに失敗させ、リトライロジックを検証。 | 障害対応能力の検証、信頼性向上 |
| **48** | スケジューラ最終検証 | `scripts/verify_scheduler.py` を実行し、`scheduler.py` の構文チェック、ユニットテスト、ヘルスチェック、統合テストを実行。`pytest` で検証。 | 最終品質保証、リリース準備完了 |

---

## 実装順序

1. **ステップ1-16** をまず実施し、DB統合と品質メトリクス改善を完了。
2. **ステップ17-32** を次に実施し、クローラーとセレクタ改善を完了。
3. **ステップ33-48** を最後に実施し、スケジューラと監視改善を完了。

各ステップは独立しており、前のステップが完了した後に次のステップに進むことができます。ステップ内でのテストも含まれているため、段階的な品質保証が可能です。

---

## ツールと技術スタック

- **言語**: Python 3.10+
- **フレームワーク**: SQLAlchemy、Alembic、APScheduler、Playwright、requests-html、BeautifulSoup
- **テスト**: pytest、MagicMock、pytest-benchmark
- **設定**: YAML、dotenv、Pydantic Settings
- **ログ**: structlog、JSON構造化ログ
- **CI/CD**: GitHub Actions、GitHub Pages
- **ドキュメント**: Markdown、MkDocs

---

## 期待される成果

1. **DB統合**: `bids_system.db` への統一、トランザクション管理の強化、マイグレーション管理の簡素化
2. **品質メトリクス**: パフォーマンス改善、メモリ使用量削減、テスト容易化、監視強化
3. **クローラー**: セレクタの堅牢性向上、非同期対応、リトライ・レート制限・プロキシサポート
4. **スケジューラ**: 例外分類、リトライポリシー、Dead Letter Queue、ヘルスチェック改善、監視ダッシュボード

---

## 完了条件

1. **ステップ1-48** の全ステップが実行完了
2. **ユニットテスト** が全ステップで90%以上カバレッジ
3. **統合テスト** が主要機能で100%パス
4. **CI/CD** が自動品質ゲートで全テストを通過
5. **ドキュメント** が各ステップで作成・更新完了

---

**作成者**: Architect Mode  
**作成日**: 2026-09-10  
**バージョン**: 1.0