# コードレビュー報告書 (再レビュー版)

**プロジェクト**: 入札システム (Bid Extraction System / nyuusatsu)  
**レビュー日**: 2026-09-11  
**レビューモード**: Architect + Runtime Verification  
**対象**: 全体アーキテクチャ、主要モジュール、テスト、CI/CD、運用

---

## 1. 概要

官公庁・自治体の入札情報を自動収集・LLM/OCRで要件抽出・正規化・可視化するエンドツーエンドシステム。クローラ基盤、品質管理、アラート、バックフィル、認証課金、スケジューラ等、多機能が統合された実用的なシステムだが、**未完了の移行作業、ランタイムで発火する NameError / ImportError、大量のバックアップファイルのコミット** など、運用直前に解決すべき Critical 問題がいくつか残っている。

## 2. Critical — 即時対応必須

| # | 項目 | ファイル | 詳細 | 影響 |
|---|------|----------|------|------|
| **C1** | **`scheduler.py` にモジュールレベル `logger` 未定義 → NameError 発火** | `scheduler.py:300,306,308,331,333,429,431,437,439` | モジュールトップには `import logging` はあるが `logger = logging.getLogger(...)` は宣言されていない。`SchedulerManager.__init__` で `self.logger` は設定されるが、`_run_forecast_crawl_async`, `_run_morning_digest_async`, `_run_backfill_async`, `_run_award_crawl_async` が**裸の `logger.xxx()`** を呼ぶ。APScheduler がこれらを実行時に即座に `NameError` でクラッシュする。 | **フォアキャスト巡回、朝ダイジェスト、バックフィル、落札クロール — すべての定期ジョブが動作不可** |
| **C2** | **`app_dashboard.py` の `from config_dir import AppConfig, PlanConfig` が ImportError** | `app_dashboard.py:23` | `config_dir.py` は `from config import AppConfig` のみ。`PlanConfig` は re-export されていない。Streamlit アプリ起動時に `ImportError` で即座にクラッシュする可能性。 | ダッシュボードアプリが起動失敗 |
| **C3** | **`db_manager.py` が独立した SQLite DB を管理** | `db_manager.py:7,38-43` | `data/crawl_history.db` に直接 `sqlite3.connect` で `crawl_history`, `crawled_urls`, `settings` テーブルを作成。しかし `database/models/crawl.py` には既に `CrawlHistory`, `CrawledUrl`, `Setting` モデルが `bids_system.db` (SQLAlchemy) に存在する。**二重管理** によりトランザクション不整、マイグレーション対象外、データ乖離リスク。 | DB整合性破綻、マイグレーション管理不能 |
| **C4** | **テスト `test_count_duplicates` / `test_count_duplicates_uses_bid_number` が no-op** | `tests/unit/test_quality_metrics_service.py:103-110,352-359` | テストが `service.count_duplicates = MagicMock(return_value=6)` で**自身をモック**してから呼び出す。実際の SQL ロジックは一切検証されない。またコメント/docstring は `bid_number` だが実装は `source_url` グルーピング。**テストが何も検証していない**。 | テストカバレッジが虚偽装備（False Confidence） |
| **C5** | **バックアップファイルが Git リポジトリにコミットされている** | `.bak`, `.bak2`, `.backup` ファイル (17件) | `services/*.bak`, `crawler/config_driven_crawler.py.backup2`, `tests/*.backup`, `docker-compose.yml.backup_redis_upgrade` 等… `.gitignore` にバックアップパターン無し。リポジトリが肥肥し上がり、**どちらが最新か不明** な状況をつくる。 | 保守性低下、誰もが混乱 |
| **C6** | **`.coverage` (77KB) と `bids_system.db` (274KB) が Git にコミット済** | プロジェクトルート | `.gitignore` には `.coverage` と `*.db` が記載されているが、既にコミット済み。バイナリアーティファクトがソースツリーに紛在。 | リポジトリ肥大化 |

## 3. High — 次スプリントで対応

| # | 項目 | ファイル | 詳細 | 影響 |
|---|------|----------|------|------|
| **H1** | **`BaseCrawler.fetch()` 同期 / `GEPSCrawler` 非同期設計不整合** | `crawler/base_crawler.py:34`, `crawler/geps_crawler.py:170` | `BaseCrawler.fetch()` は `requests.get` (同期)。`GEPSCrawler.search_bids()` は Playwright async。`crawl_range()` は sync `fetch()` を呼ぶが `GEPSCrawler` は `search_bids()` を使って `crawl_range()` をバイパス。抽象メソッド契約が形骸化。 | クローラ基盤の一貫性欠如、将来リファクタリング時の動作不確実 |
| **H2** | **`acquisition_delay_median()` が全件 `.all()` + Python ソート** | `services/quality_metrics_service.py:81-101` | クエリ結果をメモリに全ロードしてから Python でソート・中央値計算。件数が 10万件を超えると **OOM リスク + パフォーマンス劣化**。SQLite では `PERCENTILE_CONT` 非対応だが、`LIMIT/OFFSET` 分割か近似アルゴリズムで対応可。 | 大規模データ時の OOM / タイムアウト |
| **H3** | **`QualityThreshold` モデルに `lower_is_worse` カラム欠落** | `database/models/quality_threshold.py` | YAML には `lower_is_worse` キーがあるが DB モデルにはない。`seed_quality_thresholds.py` は `lower_is_worse` を無視して `warn_at`/`alert_at` のみ保存。DB フォールバック評価 (`_evaluate_db`) は `value >= threshold.alert_at` で判定 → `lower_is_worse: true` のメトリクス (e.g. `coverage_rate`) が**逆にアラート** される可能性。 | アラート判定論理の不整合 |
| **H4** | **`QualityMetric` モデルに `period_start`/`period_end` カラム欠落** | `database/models/quality_metric.py` | `collect_quality_metrics.py` が収集期間をメトリクスレコードに残さない。後から「いつの期間のメトリクスか」判別不可。 | メトリクス監査・再現性不可 |
| **H5** | **`BaseCrawler._filter_by_date_range` が `extract_item_date` を抽象メソッドにしていない** | `crawler/base_crawler.py:110-113` | `getattr(self, "extract_item_date", None)` で存在チェックのみ。未実装サブクラスは**警告一つでサイレントスキップ** → フィルターが効いていないことに気づかない。 | データ品質低下（日付フィルタ回避） |
| **H6** | **スケジューラジョブの `except Exception` 握りつぶし** | `scheduler.py:100,124,184,220,308,333,355,377,431,439,449` | 全ジョブで `except Exception as e: logger.error(...)` で継続。DB接続不可等の **Critical エラーでも無限リトライ・リソース枯渇** リスク。例外分類（Transient/Fatal） + 指数バックオフ + 最大リトライ未実装。 | 障害時の無限ループ・リソース枯渊 |
| **H7** | **`pytest.ini` の `--cov=geps_crawler.py` パス指定不正** | `pytest.ini:4` | `geps_crawler.py` は `crawler/` サブディレクトリにある。`--cov=geps_crawler.py` は**モジュールパス指定**が間違っておりカバレッジ対象にならない可能性。`--cov=crawler.geps_crawler` または `--cov=crawler` が正しい。 | カバレッジ測定不正確 |
| **H8** | **GEPS セレクタヒューリスティックが `input[type="date"]` を複数フィールド候補に含む** | `crawler/geps_crawler.py:119-126` | ヒューリスティックリストに `input[type="date"]` が含まれているが、これは**date 入力フィールドすべて**にマッチする。開始日フィールドも終了日フィールドも `input[type="date"]` に反応 → **`_find_date_field` が常に最初の `input[type="date"]` を返し、終了日フィールドが取得不可能**になる可能性。 | 日付範囲フィルター不可 |

## 4. Medium — 技術的負債・保守性

| # | 項目 | ファイル | 詳細 | 影響 |
|---|------|----------|------|------|
| **M1** | **Quality モデルが独自 `declarative_base()` を各自生成** | `database/models/quality_metric.py:5`, `quality_threshold.py:4`, `quality_alert.py:5` | 3つのファイルがそれぞれ `Base = declarative_base()` を生成。`database/models/__init__.py` で `create_all_quality_tables()` を用意して回避しているが、`Base.metadata.create_all()` では quality テーブルが作成されない。**メタデータ断裂** リスク。Alembic 自動生成にも影響。 | マイグレーション管理複雑化 |
| **M2** | **`REQUIRED_FIELDS` がハードコードされ `Bid` モデルと乖離** | `services/quality_metrics_service.py:12-20` | `organization_name` は `Bid` に存在するが `prefecture_code` は `String` カラムとして存在。しかし `Bid` モデルには `prefecture_code` がある (line 170)。逆に `announcement_date` は `DateTime` だが `count_missing_fields` が `getattr(Bid, field) == None` でフィルタ → **None 比較の SQLAlchemy クエリは `IS NULL` に変換される** が、`is_` を使うべき。 `==` は一部 DBAPI で問題を起こす可能性。 | メトリクス正確性 |
| **M3** | **`QUALITY_THRESHOLDS_PATH` デフォルトが相対パス** | `services/quality_alert_service.py:16` | `_DEFAULT_THRESHOLDS_PATH = "config/quality_thresholds.yaml"` — CWD 依存。Docker コンテナや CI で CWD が異なる場合 **ファイルが見つからない**。 `Path(__file__).parent.parent / "config" / ...` にすべき。 | 運用環境でしきい値読み込み失敗 |
| **M4** | **`QualityAlertService._db_threshold()` が `alert_at` のみ返す** | `services/quality_alert_service.py:67-74` | DB フォールバックで `warn_at` は無視。YAML と DB で**評価ロジックが不一致**。`lower_is_worse` も考慮されない。 | しきじょう評価の不整合 |
| **M5** | **`GEPSCrawler.__init__` で `_load_selectors()` を即座に呼ぶ** | `crawler/geps_crawler.py:48` | コンストラクタで YAML ファイルを即読み込み。ファイル不存在時は **コンストラクタ例外**。テストやファイル未配置環境でインスタンス化不可能。遅延ロード（プロパティ）にすべき。 | テスト・デプロイの脆弱性 |
| **M6** | **`crawler/geps/award_crawler.py` が `crawler/geps_crawler.py` と重複** | `crawler/geps/award_crawler.py` vs `crawler/geps_crawler.py` | 2つの GEPS クローラ実装が存在。`geps_crawler_updated.py` も別途存在。**3 つの実装** が混在し、どれが本命か不明。 | 混乱・保守費用増 |
| **M7** | **`config.py` に `from dataclasses import field` の重複 import** | `config.py:2,4` | `from dataclasses import dataclass, field` (L2) と `from dataclasses import field` (L4) の**重複**。Linter 警告。 | マイナー |
| **M8** | **`health_checker.py:93` `session.execute("SELECT 1")` — SQLAlchemy 2.0 非互換** | `services/health_checker.py:93` | `future=True` エンジンで生 SQL を `text()` 無しで実行。SQLAlchemy 2.0 では `DeprecationWarning` または `CompileError` を引き起こす可能性がある。 | ヘルスチェック不具合 |

## 5. Low — 改善・拡張

| # | 項目 | ファイル | 詳細 |
|---|------|----------|------|
| **L1** | **`db_manager.py` に型ヒントなし** | `db_manager.py` | すべての関数が型注釈なし。`mypy` 導入検討。 |
| **L2** | **`BaseCrawler` の `backoff` にジッターなし** | `crawler/base_crawler.py:45` | `time.sleep(self.backoff * (2 ** attempt))` — ジッター無しで**バーストリトライ**リスク。`+ random.uniform(0, 0.5)` を追加。 |
| **L3** | **`QualityAlertService.send_alert()` が両チャネル失敗でも `True` を返す可能性** | `services/quality_alert_service.py:186-189` | 実装を見ると**両方失敗時のみ `False`** 返す。レビュー報告書の指摘は**不正確**（コードを再確認）。 |
| **L4** | **`pytest.ini` `addopts` に `--cov-fail-under=10` が極端に低い** | `pytest.ini:5` | 10% は実質的に **no-op**。最低でも 70% に引き上げるべき。 |
| **L5** | **`test_quality_metrics_service.py` のモックが過度に複雑・実装結合** | `tests/unit/test_quality_metrics_service.py:13-30` | `make_query_chain` は `query.side_effect` で呼び出し順に依存。リファクタリング一発で壊れる。 |
| **L6** | **`app.py` で `ExtractionResultRepository` の import 重複** | `app.py:17,25` | `from database.repositories.extraction_result_repository import ExtractionResultRepository` が **2 回** import されている。 |
| **L7** | **`.env.example` に改行コード不整** | `.env.example` | ファイル末尾に改行がない (`RATES_LIMIT_REQUESTS_PER_MIN=10` の直後に `===` が続く)。 |

## 6. CI / CD

| 項目 | 詳細 | 評価 |
|------|------|------|
| **CI ワークフロー** | `.github/workflows/ci.yml` と `test.yml` が**重複**。前者は構造化 CI、後者は簡易 CI。両方が `push`/`pull_request` トリガー。 | 統一すべき |
| **Flake8 F821 チェック** | `test.yml` が `flake8 --select=E9,F63,F7,F82` を実行。`scheduler.py` の `logger` 未定義 (F821) **を検知可能**。CI がグリーンなのか確認要。 | ⚠️ 未検証 |
| **Live Tests** | `.github/workflows/live-tests.yml` は週1スケジュール + 手動実行。Playwright ブラウザインストール、レポートアップロード、Slack 通知完備。 | 良好 |
| **pytest.ini addopts** | `--cov=crawler --cov=geps_crawler.py --cov=config.py --cov=services --cov=repositories` — `geps_crawler.py` パス不正 (H7)。 | 要修正 |
| **Coverage target** | `--cov-fail-under=10` / `.coveragerc` `fail_under = 0` — 実質カバレッジ強制なし。 | 要改善 |

## 7. セキュリティ・コンプライアンス

| 項目 | 現状 | 推奨 |
|------|------|------|
| **APIキー** | `.env.example` にプレースホルダー。`config.py` にハードコードされたデフォルトユーザー (`admin`/`changeme123`) | `.env.example` のみコミット、デフォルトユーザー削除 |
| **DB内平文パスワード** | `BidSource` モデルに `username`/`password` プレインテキストカラム | 暗号化または外部シークレット管理 |
| **SQLインジェクション** | `db_manager.py` は生 SQL なし (parameterized)。`health_checker.py:93` は固定文字列。SQLAlchemy ORM メインで安全。 | そのまま |
| **認証** | `app_admin.py` は `is_authenticated()` チェックなし (コード L80-80 参照)。`app_dashboard.py` も同様に `PlanConfig` import エラーレベル。 | RBAC 強制 |
| **依存脆弱性** | `pip-audit` を CI で実行 (test.yml)。`requirements_lock.txt` 存在するが `requirements.txt` は未ロック。 | lock ファイルで CI 固定 |

## 8. アーキテクチャ評価

### 8.1 良点
- **関心の分離**: `crawler/`, `services/`, `database/`, `app/` が明確に分離
- **Repository パターン**: `database/repositories/__init__.py` と `database/repositories/base.py` で CRUD を抽象化
- **設定駆動**: `config_driven_crawler.py`, `quality_thresholds.yaml`, `targets.yaml` で運用パラメータ外部化
- **品質メトリクス層**: 欠損率、重複率、取得遅延、カバレッジ率、日次デルタを網羅
- **ライブテストインフラ**: `tests/test_geps_live/` に 6フェーズ 40+ テストケース、並列・タイムアウト・リトライ・レポート生成完備

### 8.2 課題
- **DB 層の断裂**: `db_manager.py` (raw sqlite3 + `crawl_history.db`) vs SQLAlchemy (`bids_system.db`) — **C3**
- **クローラ基盤の同期/非同期混在**: `BaseCrawler` (sync requests) vs `GEPSCrawler` (async Playwright) — **H1**
- **Quality モデルのメタデータ断裂**: 3つの `declarative_base()` — **M1**
- **3つの GEPS クローラ実装**: `geps_crawler.py`, `geps_crawler_updated.py`, `crawler/geps/award_crawler.py` — **M6**

## 9. 実装計画 P3 進捗 (再評価)

| Phase | Step | 状況 | 備考 |
|-------|------|------|------|
| **Phase 1: ライブテスト自動化** | 1-12 | ✅ ほぼ完了 | `conftest.py` に `live_test_dir` fixture + `pytest_runtest_makereport` フック + `cleanup_live_test_resources` fixture 実装済み。`targets.yaml` 外部化完了。`.github/workflows/live-tests.yml` 存在。 |
| **Phase 2: GEPSセレクタ堅牢化** | 13-24 | ⚠️ **部分的(13-18, 22-24 完)** | Step 13-17 (外部化・バージョニング・フォールバック) **完了** (`geps_selectors.yaml`, `_load_selectors`, `_selector_candidates`, `_select_one`, `_select_all` 実装済み)。Step 18 (日付自動検出) **完了** (`_find_date_field` 実装済み)。Step 20-21 (フィクスチャ・回帰テスト) **完了** (`tests/fixtures/geps/` に 4 HTML フィクスチャ, `tests/unit/test_geps_selectors.py` 実装済み)。Step 22 (実サイト統合テスト) **完了** (`scripts/test_geps_live.py` 存在, Phase 5-6 ライブテスト 15+ ケース)。 **注意: Step 18 のヒューリスティックに `input[type="date"]` 重複問題 (H8)** |
| **Phase 3: 品質メトリクス・アラート完全動作** | 25-36 | ✅ **大部分完了** | Step 25-26 (収集・cron) **完了**。Step 27 (閾値外部化) **完了**。Step 28-30 (通知・重複抑制・履歴保存) **完了**。Step 31-32 (管理画面・ダッシュボード) **実装済み** (`app_admin.py:30` タブ10, `app_dashboard.py:54` タブ)。 Step 33-36 (ヘルプ・テスト・ドキュメント) — テスト **実装済み** (`test_quality_metrics_service.py`, `test_quality_metrics_alert_flow.py`)、**H4 の `period_start/end` 欠落**。 |

## 10. アクションプラン (優先度順)

### 即時（1-2日）
1. [ ] **`scheduler.py` に `logger = logging.getLogger(__name__)` を追加** (C1) — `_run_forecast_crawl_async`, `_run_morning_digest_async`, `_run_backfill_async`, `_run_award_crawl_async` がクラッシュしている
2. [ ] **`config_dir.py` に `PlanConfig` を re-export** (C2) — `from config import AppConfig, PlanConfig` に修正
3. [ ] **バックアップファイル (`.bak`, `.bak2`, `.backup`) を Git から削除** (C5) — `.gitignore` に `*.bak` を追加
4. [ ] **`bids_system.db`, `.coverage` を `.gitignore` に追加** (C6) — Git から削除
5. [ ] **`test_count_duplicates` / `test_count_duplicates_uses_bid_number` を実装に即したテストに書き直し** (C4)

### 短期（1-2週間）
6. [ ] `db_manager.py` を SQLAlchemy `CrawlHistory`/`CrawledUrl`/`Setting` モデルに移行 (C3)
7. [ ] `QualityThreshold` に `lower_is_worse` カラム + マイグレーション (H3)
8. [ ] `QualityMetric` に `period_start`/`period_end` カラム + 収集スクリプト修正 (H4)
9. [ ] `acquisition_delay_median()` を SQL 分割計算に最適化 (H2)
10. [ ] `BaseCrawler.extract_item_date` を `@abstractmethod` 化 (H5)
11. [ ] `pytest.ini` の `--cov=geps_crawler.py` を `--cov=crawler` に修正 (H7)
12. [ ] `_find_date_field` の `input[type="date"]` 重複候補問題を修正 (H8)
13. `QualityAlertService` に Redis クライアント DI 導入 (既存レビュー通り)
14. スケジューラジョブの例外分類・リトライポリシー導入 (H6)

### 中期（1ヶ月）
15. Quality モデルの `declarative_base()` を統一 (M1)
16. `QUALITY_THRESHOLDS_PATH` を絶対パス化 (M3)
17. 3つの GEPS クローラ実装を統合 (M6)
18. `mypy` / `ruff` CI 強化
19. `config.py` の重複 import クリーンアップ (M7)
20. `health_checker.py` の `text()` 修正 (M8)

---

## 11. 総評

本プロジェクトは **機能的には高い完成度** だが、**運用直前に発火する NameError (C1) と ImportError (C2)** が 2 件あり、**即座に対応しないと本番環境（特に Docker の scheduler コンテナ）が起動失敗する**。

次に大きなリスクは **バックアップファイルの乱立 (C5)** と **db_manager.py の二重DB管理 (C3)**。これらは早期に解消することで保守コストを大幅に削減できる。

P3 計画の実装状況は **コードレビュー報告書の評価より進んでいる** (Phase 2 のセレクタ外部化、フィクスチャ、回帰テストは既に実装済み)。ただし **H8 (ヒューリスティック重複)** と **H4 (メトリクス期間未記録)** など、実装済み機能にも潜在的な論理バグが存在する。

---

**レビュー完了**  
次ステップ: C1, C2, C5, C4 を優先に即日修正し、CI をグリーンにすることを推奨。
