# コードレビュー報告書

**プロジェクト**: 入札システム (Bid Extraction System)  
**レビュー日**: 2026-09-10  
**レビューモード**: Architect  
**対象**: 全体アーキテクチャ、主要モジュール、テスト、実装計画 P1-P3

---

## 1. 概要

本プロジェクトは、官公庁・自治体の入札情報を自動収集し、LLM/OCRで要件抽出・正規化・可視化するエンドツーエンドシステムです。クローラ基盤、品質管理、アラート、バックフィル、認証課金、スケジューラ等、多機能が統合されています。

レビュー対象ファイル（主要）:
- `db_manager.py` - 簡易SQLite履歴DB
- `crawler/base_crawler.py` - クローラ基底クラス（日付範囲フィルタ対応）
- `services/quality_metrics_service.py` - 品質メトリクス収集
- `services/quality_alert_service.py` - 品質アラート評価・通知
- `scheduler.py` - APSchedulerジョブ管理
- `tests/unit/test_quality_metrics_service.py` - 単体テスト
- `config/quality_thresholds.yaml` - しきい値設定

---

## 2. 良い点

### 2.1 アーキテクチャ・設計
- **関心の分離**: `crawler/`、`services/`、`database/`、`app/` が明確に分離
- **基底クラス活用**: `BaseCrawler` に共通ロジック（リトライ、日付フィルタ、早期終了）を集約
- **設定駆動**: `config_driven_crawler.py`、YAML設定（`quality_thresholds.yaml`）で運用パラメータを外部化
- **スケジューラ統合**: APSchedulerでクロール、ヘルスチェック、品質収集、バックフィル等を一元管理

### 2.2 品質管理機能
- **多層メトリクス**: 欠損率、重複率、取得遅延中央値、カバレッジ率、日次デルタを網羅
- **二重しきい値**: YAML（`quality_thresholds.yaml`）+ DB（`QualityThreshold`）のフォールバック
- **重複抑制**: Redis TTL 24h で同一日同一メトリクスの多重通知を防止
- **履歴保存**: `QualityAlert` モデルでアラート履歴をDB保存、管理画面で閲覧可能

### 2.3 テスト
- `tests/unit/test_quality_metrics_service.py` で主要メソッドをモックベースで網羅
- `pytest` + `MagicMock` でDB非依存の高速テストを実現
- GEPSライブテスト（`tests/test_geps_live/`）で実環境検証の仕組みを整備

### 2.4 運用考慮
- `--date-range` で過去分再収集対応（`collect_quality_metrics.py`）
- 朝ダイジェスト、ヘルスチェック、メトリクスクリーンアップ等、運用ジョブを網羅
- Slack/LINE 両チャネル通知対応

---

## 3. 改善提案（優先度順）

### 🔴 Critical（即時対応推奨）

| # | 項目 | 詳細 | 推奨アクション |
|---|------|------|----------------|
| C1 | **`db_manager.py` が本番DBと別系統** | `data/crawl_history.db` を直接操作。メインの `bids_system.db` (SQLAlchemy) と分離されており、トランザクション整合性・マイグレーション管理の対象外 | `database/models/` へ統合し、Alembic管理下に置く。`CrawlHistory`/`CrawledUrl` モデルが既に `_generated.py` に存在するため、こちらを使用するよう移行 |
| C2 | **`BaseCrawler.fetch()` が同期 `requests` 使用** | 非同期クローラ（`geps_crawler.py` は Playwright 使用）と混在。スレッドブロッキングの原因になり得る | 非同期版 `async_fetch()` を追加、または `httpx.AsyncClient` へ統一。既存同期コードは `run_in_executor` でラップ |
| C3 | **`QualityMetricsService.acquisition_delay_median()` が全件メモリ読み込み** | `q.all()` で全レコード取得後 Python でソート。件数増大時 OOM リスク | SQL 側で `PERCENTILE_CONT(0.5)` (PostgreSQL) または近似アルゴリズムを使用。SQLite の場合は `LIMIT/OFFSET` で分割計算 |
| C4 | **`QualityAlertService._check_redis_dedupe()` が `redis_conn` 直接参照** | `database.redis_conn.redis_conn` がグローバルシングルトン。テスト時モック困難、接続プール管理不在 | 依存性注入（DI）で `redis_client` を渡す設計に変更。`__init__` で受け取るか、プロトコル定義 |

### 🟠 High（次スプリントで対応）

| # | 項目 | 詳細 | 推奨アクション |
|---|------|------|----------------|
| H1 | **`QualityThreshold` モデルに `lower_is_worse` なし** | YAML には `lower_is_worse` があるが、DB モデルに同等フィールドがない。フォールバック時挙動不一致 | `QualityThreshold` に `lower_is_worse` カラム追加、マイグレーション作成 |
| H2 | **`collect_quality_metrics.py` が `QualityMetric` に `recorded_at` 自動設定のみ** | 収集対象期間（`date_start`/`date_end`）がメトリクスレコードに残らない。後から「いつの期間のメトリクスか」判別不可 | `QualityMetric` に `period_start`/`period_end` カラム追加、収集時に記録 |
| H3 | **GEPSクローラのセレクタがハードコード/プレースホルダ** | `geps_crawler.py:135-145` で `input[placeholder*="開始"]` 等の脆弱セレクタ使用。P3 Step 13-17 で外部化予定だが未完了 | `crawler/config/geps_selectors.yaml` 作成し、`_load_selectors()` 実装。バージョニング（`selectors_version`）導入 |
| H4 | **`BaseCrawler._filter_by_date_range` が `extract_item_date` 必須だが強制されない** | 抽象メソッドでなく `getattr` チェックのみ。実装漏れ時にサイレントスキップ（警告のみ） | `extract_item_date` を `@abstractmethod` 化、または `NotImplementedError` 送出 |
| H5 | **スケジューラジョブのエラーハンドリングが `except Exception` で握りつぶし** | `scheduler.py` 全ジョブで `logger.error` 後継続。クリティカルエラー（DB接続不可等）で無限リトライ・リソース枯渇リスク | 例外分類（`TransientError`/`FatalError`）導入、指数バックオフ+最大リトライ、Dead Letter Queue 的仕組み |

### 🟡 Medium（技術的負債・保守性）

| # | 項目 | 詳細 | 推奨アクション |
|---|------|------|----------------|
| M1 | **`database/models/__init__.py` が `_generated.py` から再エクスポート** | 自動生成モデルと手動モデル（`quality_metric.py` 等）が混在。生成元（`bids_system.db`）との乖離リスク | Alembic 自動生成（`alembic revision --autogenerate`）へ完全移行、手動モデルも migration 管理下に |
| M2 | **`QualityMetricsService.REQUIRED_FIELDS` がハードコード** | `Bid` モデル変更時に追従漏れリスク | `Bid.__table__.columns` から `nullable=False` なカラムを動的取得、または設定ファイル化 |
| M3 | **`geps_crawler.py` でブラウザ初期化・クローズを各メソッドで繰り返し** | `search_bids`、`fetch_pdf_links` それぞれで `init_browser`/`close`。リソース効率悪、並列実行時競合 | コンテキストマネージャ（`async with`）化、またはセッションプール導入 |
| M4 | **テストフィクスチャが `tests/test_geps_live/` に実HTML保存予定だが未実装** | P3 Step 20「単体テスト用 HTML フィクスチャ追加」未着手。回帰テスト不可 | 実HTML取得スクリプト作成、`tests/fixtures/geps/` へ保存、CI でコミット |
| M5 | **`config/quality_thresholds.yaml` の `daily_new`/`daily_updated` しきい値が 0** | `lower_is_worse: true` で 0 以下ならアラート。実質無効。意図不明 | 実運用値に基づき適切な閾値設定、または削除・コメントアウト |

### 🟢 Low（改善・拡張）

| # | 項目 | 詳細 | 推奨アクション |
|---|------|------|----------------|
| L1 | **`db_manager.py` に型ヒントなし** | 関数シグネチャに型注釈なし。静的解析・IDE支援弱い | 全関数に型ヒント追加、`mypy` 導入検討 |
| L2 | **`BaseCrawler` の `backoff` が指数的だがジッターなし** | 同一時刻に複数クローラがリトライするとバースト | `backoff * (2 ** attempt) + random.uniform(0, 0.5)` 等ジッター追加 |
| L3 | **`QualityAlertService.send_alert()` が Slack/LINE 両方送信し、片方失敗でも `True` 返却** | 片方失敗を「成功」とみなす設計。通知到達保証弱い | 成否を個別記録、両方失敗時のみ `False`。成功時は `{"slack": true, "line": false}` 等詳細返却 |
| L4 | **`scheduler.py` で `get_db()` ジェネレータを `with` で使用** | `get_db()` は `yield` するジェネレータ。`with get_db() as session:` は動作するが意図不明確 | `get_session()` 統一、または `contextmanager` デコレータ明示 |
| L5 | **`tests/unit/test_quality_metrics_service.py` のモックが過度に複雑** | `mock_session.query.side_effect` 等で内部実装に強結合。リファクタリング時壊れやすい | インターフェース（`BidRepository` 等）抽出し、モックをリポジトリレベルで実装 |

---

## 4. 実装計画 P3 進捗確認

| Phase | Step | 状況 | 備考 |
|-------|------|------|------|
| **Phase 1: ライブテスト自動化** | 1-12 | **概ね完了** | `tests/test_geps_live/conftest.py` に `live_test_dir` fixture、`run_live_tests.py` にレポート生成・並列・タイムアウト・リトライ実装済み。GitHub Actions (`.github/workflows/live-tests.yml`) 要確認 |
| **Phase 2: GEPSセレクタ堅牢化** | 13-24 | **未着手〜部分的** | Step 13-17（外部化・バージョニング・フォールバック）未実装。Step 18（日付自動検出）は `_set_date_range` で部分的実装。Step 20-21（フィクスチャ・回帰テスト）未着手 |
| **Phase 3: 品質メトリクス・アラート完全動作** | 25-36 | **大部分実装済み** | Step 25-26（収集・cron）完了。Step 27（閾値外部化）YAML完了、DBフォールバック実装済み。Step 28-30（通知・重複抑制・履歴保存）完了。Step 31-32（管理画面・ダッシュボード）`app_admin.py` にタブ実装済み。Step 33-36（ヘルプ・テスト・ドキュメント）要確認 |

---

## 5. アーキテクチャ改善提案（中長期）

### 5.1 データベース層の統一
```
現状: db_manager.py (sqlite3直) + SQLAlchemy (bids_system.db) + Alembic
提案: 全テーブルを SQLAlchemy + Alembic 管理下に統一
      - CrawlHistory, CrawledUrl, Settings をモデル化し migration 作成
      - db_manager.py を repository パターンでラップし段階的移行
```

### 5.2 クローラ基盤の非同期化・統一
```
現状: BaseCrawler (同期requests) + GEPSCrawler (Playwright async) + 多数の個別クローラ
提案: 
  - BaseCrawler を Protocol 定義し、sync/async 両実装を許容
  - 共通リトライ・レート制限・プロキシを `crawler/utils/` にミドルウェア化
  - Playwright/HTTPX 使い分けを戦略パターンで注入
```

### 5.3 品質メトリクスのストリーミング集計
```
現状: 日次バッチで全件スキャン・集計
提案: 
  - 挿入時トリガー/イベント駆動で増分更新
  - Redis HyperLogLog / t-Digest で近似メトリクスをリアルタイム維持
  - 日次バッチは検証・補正用に限定
```

### 5.4 設定管理の一元化
```
現状: config.py, config_dir.py, .env, YAML複数, DB設定テーブル が混在
提案: 
  - Pydantic Settings で全設定を型安全に統合
  - 環境別（dev/staging/prod）プロファイル対応
  - 機密値は Secret Manager / Vault 連携
```

---

## 6. セキュリティ・コンプライアンス観点

| 項目 | 現状 | 推奨 |
|------|------|------|
| **APIキー管理** | `.env` ファイル直置き | 本番は Secret Manager、`.env.example` のみコミット |
| **SQLインジェクション** | SQLAlchemy ORM 主体で安全。`db_manager.py` の生SQLのみリスク | `db_manager.py` も ORM 移行で解消 |
| **認証・認可** | `app_billing.py` で Stripe 連携、Flask 管理画面に基本認証 | RBAC（`Role` モデル存在）を全エンドポイントで強制、API トークン認証追加 |
| **監査ログ** | `AuditLog` モデル存在 | 重要操作（設定変更、データ削除、アラート抑制）を自動記録 |
| **依存脆弱性** | `requirements_lock.txt` 存在 | `pip-audit` / `dependabot` で定期スキャン自動化 |

---

## 7. 具体的アクションプラン（優先度順）

### 即時（1-2日）
1. [ ] `db_manager.py` → SQLAlchemy モデル移行（`CrawlHistory`, `CrawledUrl`, `Setting`）
2. [ ] `QualityThreshold` に `lower_is_worse` カラム追加・マイグレーション
3. [ ] `QualityMetric` に `period_start`/`period_end` 追加・収集スクリプト修正
4. [ ] `BaseCrawler.extract_item_date` を `@abstractmethod` 化

### 短期（1-2週間）
5. [ ] GEPS セレクタ外部化（`crawler/config/geps_selectors.yaml` + ローダー）
6. [ ] `QualityAlertService` に Redis クライアント DI 導入
7. [ ] `acquisition_delay_median` を SQL 側集計化（または分割処理）
8. [ ] スケジューラジョブの例外分類・リトライポリシー導入
9. [ ] テストフィクスチャ（GEPS 実HTML）取得・コミット・回帰テスト作成

### 中期（1ヶ月）
10. [ ] 全モデル Alembic 管理下へ統一、`_generated.py` 廃止
11. [ ] 非同期クローラ基盤統一（HTTPX + Playwright 戦略パターン）
12. [ ] 品質メトリクス増分更新（イベント駆動）設計・実装
13. [ ] Pydantic Settings 導入・設定一元化
14. [ ] `mypy` / `ruff` 導入・CI 組み込み

---

## 8. 総評

本プロジェクトは**機能豊富で実用的なシステム**として高い完成度を持ちます。特に品質管理・アラート・スケジューラ周りは運用視点でよく設計されています。

**最大のリスク**は `db_manager.py` の二重DB管理と、クローラ基盤の同期/非同期混在です。これらは早期に解消することで、スケール時の障害・保守コストを大幅に削減できます。

P3 計画のうち Phase 1（ライブテスト自動化）はほぼ完了しており、Phase 2（GEPS堅牢化）への着手が次のマイルストーンとして適切です。Phase 3 はコア機能が実装済みで、UI・ドキュメント・テスト拡充で完了見込みです。

---

**レビュー完了**  
次ステップ: 上記アクションプランを Issue 化し、優先度順に実装着手を推奨