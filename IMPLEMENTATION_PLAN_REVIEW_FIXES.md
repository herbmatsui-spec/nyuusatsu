# 実装計画書：入札システム コードレビュー是正

作成日: 2026-08-28
方針: レビューで発覚したブロッカーを優先し、プロジェクトを「import 可能・起動可能」な状態へ復元する。
実 DB（`bids_system.db`：44テーブル）のスキーマを正ソースとし、`database` パッケージを再構成する。

---

## Phase 0: 前提とリスク
- リポジトリには `database` パッケージが存在せず、アプリ/サービス/crawler/queue/scheduler 計 **142ファイル + テスト22ファイル** が `database.*` を import しているため全滅していた。
- 元の `database` パッケージ実体（リレーション定義・repositories の厳密なメソッド API）は失われている。
- 本計画では「import 解決 + 実 DB へのマッピング」を確実に行い、ランタイムの厳密互換は元ソースが見つかるまでベストエフォートとする。

---

## Phase 1: database パッケージ再構成（最重要・本実装）

### 1.1 接続層
- `database/engine.py`
  - `DATABASE_URL` は env 優先、既定 `sqlite:///./bids_system.db`
  - SQLite は `check_same_thread=False`、`future=True`
- `database/session.py`
  - `SessionLocal = sessionmaker(...)`、`scoped_session` 提供
  - `get_db()` ジェネレータ（FastAPI/Streamlit 互換）
  - `get_session()` は `SessionLocal()` を返す（with 利用可）
- `database/redis_conn.py`
  - `REDIS_URL` から `redis.Redis.from_url`、未設定時は `None`

### 1.2 モデル層（自動生成）
- `bids_system.db` を `PRAGMA table_info` / `foreign_key_list` で内省し、
  `database/models/_generated.py` に全44テーブルの SQLAlchemy 2.0 モデルを生成。
- 型マッピング: INTEGER→Integer, TEXT→Text, VARCHAR(n)→String(n), REAL→Float,
  BLOB→LargeBinary, NUMERIC→Numeric, BOOLEAN→Boolean, DATETIME→DateTime。
- クラス名は CamelCase 単数形（agencies→Agency 等）。
- コードが要求する `from database.models.<sub>.import <Name>` の全名を満たすよう、
  サブモジュール（`agency.py` / `bid.py` / `crawl.py` / `procurement_forecast.py` 等）で再エクスポート。
- 要求モデル一覧（インポート実績から抽出）:
  Agency, AgencyCategory, CrawlConfig, AlertHistory, Competitor, AwardResult, AwardHistory,
  Bid, BidQualificationTag, QualificationTag, CompanyProfile, CompanyRegionRank, Customer,
  Partner, CustomerBidLink, PartnerBidLink, BidStatus, Prefecture, BidSource, SystemSetting,
  CrawlHistory, CrawledUrl, CrawlLog, AuditLog, DocumentArchive, ExtractionResult,
  ForecastStatusEnum, CustomerForecastLink, ForecastAlertConfig, ProcurementForecast,
  ForecastStatus, Role, UserRole, SavedSearch, URLRegistry, User, Organization, PDFDocument,
  PipelineMetric, PipelineRun, BidAssignment, NotificationChannel

### 1.3 リポジトリ層
- `database/repositories/__init__.py`: `save_bid(session, data, full_text)` / `save_bids_batch(session, records, texts)`
- 各サブモジュールで要求クラスを提供（薄い汎用 CRUD ベース）:
  BidRepository, PDFRepository, AgencyRepository, ExtractionResultRepository,
  FavoriteRepository, SavedSearchRepository, NotificationChannelRepository,
  CustomerRepository, PartnerRepository, AwardResultRepository
- コンストラクタは `(session)` を受け `self.session` / `self.model` を保持。

### 1.4 検証
- システム Python（sqlalchemy 2.0.52 導入済）で全モデル import 成功を確認。
- 各モデルのカラム名が実 DB の `PRAGMA table_info` と一致することを自動検証。

---

## Phase 2: 設定・環境の修正
- `alembic.ini` の `script_location = %(here)s/alembic` → `migrations`（実ディレクトリに合わせる）。
- `requirements.txt` をピン留め（実環境から `==` 固定化し `requirements_lock.txt` を更新）。
- `.venv` 再構築（現在 `.venv/bin` が空で壊れている）。`.venv_fixed` との統合。
- 不要ファイル削除: 文字化け `$null`、不要な `*.backup_*` DB（gitignore 済みだが作業-tree に残る）。

---

## Phase 3: コード品質の是正
- `print()` 519箇所 → `logging` へ（優先: crawler/service 層の主要モジュール）。
- `except Exception` 280箇所 / bare `except:` 5箇所 → 具体的例外へ絞り込み、最低限 `logger.error` を義務化。
  対象: `app_observability.py:200`, `services/metrics_query_service.py:114`,
  `services/crawl_scheduler.py:198/259`, `crawler_task.py:43`
- GEPS クローラ重複解消: `geps_crawler.py`（ライブテストのみ）と `geps_crawler_updated.py`（本番スクリプト利用）の
  統合方針を決定し、非推奨側に deprecation 明記。
- `verify_db.py:40` の f-string SQL（`PRAGMA table_info({tbl})`）をパラメータ化/ホワイトリスト化。
- `pytest.ini` の `--cov=geps_crawler.py` をモジュール名 `geps_crawler` に修正。

---

## 実施順（このセッションで行う範囲）
1. Phase 1.1〜1.4（database パッケージ再構成＋検証）← 今回実装
2. Phase 2 の alembic 修正 ＋ `$null` 削除
3. Phase 3 の bare except 5箇所修正 + print→logging を主要数ファイルに適用
4. 残り（requirements ピン留め・venv 再構築・GEPS統合・広域 except 一掃）は継続タスクとして報告

## 完了判定
- `python -c "import database.models, database.session, database.engine, database.redis_conn, database.repositories"` が成功。
- 142ファイルのうち `database.*` を import するモジュールが import エラーにならないこと（構文・パス解決のみ；
  個別メソッドの厳密互換は元ソース確認後に追跡）。
