# 入札情報バックフィル（過去データ遡及取得）システム — 72ステップ実装計画書

> **目標**: 既にクロール済みの発注機関について、過去2年分以上の入札履歴を遡及取得し、重複排除・整合性修正を行ってDBに蓄積する。日次クロールでは取りこぼした過去案件を確実に取得する。
> **前提**: Python 3.14, SQLite, Playwright/Chromium導入済み, 既存クローラ基盤（BaseCrawler, GenericCrawler, GEPSCrawler）が稼働中
> **方針**: 低性能LLMでも実装できるよう、各ステップを「単一ファイル・単一関数」レベルまで細分化

---

## Phase 0 — 事前調査・設計 (ステップ 1–8)

### 0-1. 現状確認・要件定義

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 1 | 既存クローラの日付範囲対応確認 | `BaseCrawler`, `GenericCrawler`, `GEPSCrawler` が日付指定巡回に対応しているか確認 | `crawler/base_crawler.py` 等 |
| 2 | 既存Bidモデルの日付フィールド確認 | `announcement_date`, `created_at`, `updated_at` 等の日付フィールドの現状確認 | `database/models/bid.py` |
| 3 | 既存CrawlConfigの頻度設定確認 | `crawl_configs.frequency` が daily/weekly/monthly 等で設定されているか確認 | `database/models/crawl_config.py` |
| 4 | 重複判定キーの確認 | `source_url` で重複排除しているか、`BidSource` との関係確認 | `database/models/bid.py`, `bid_source.py` |
| 5 | 対象発注機関の抽出条件整理 | バックフィル対象とするAgencyの条件（is_crawled=True かつ is_active=True 等）を定義 | — |
| 6 | 過去データの取得可能範囲調査 | 各サイトで過去何年分まで遡れるか、ページネーションの限界を調査 | — |
| 7 | 既存マイグレーション履歴確認 | `alembic/versions/` の最新リビジョンとDBスキーマの整合性確認 | `alembic/versions/` |
| 8 | エラーハンドリング方針決定 | 取得失敗時のリトライ・スキップ・ログ記録のルールを文書化 | — |

---

## Phase 1 — バックフィル用ジョブモデルの構築 (ステップ 9–18)

### 1-1. データモデル作成

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 9 | BackfillJobモデルの作成 | `database/models/backfill_job.py` 新規作成。カラム: `id`, `agency_id`, `start_date`, `end_date`, `status`, `fetched_count`, `error_message`, `created_at`, `updated_at` | `database/models/backfill_job.py` |
| 10 | BackfillJobのenum定義 | `status` 用の Enum クラス `BackfillJobStatus` 作成（pending/running/done/failed/skipped） | `database/models/backfill_job.py` |
| 11 | BackfillJobのリレーション追加 | `agency_id` を `Agency.id` への FK に設定、`Agency` モデルに `backfill_jobs` リレーション追加 | `database/models/backfill_job.py`, `database/models/agency.py` |
| 12 | BackfillJobLogモデルの作成 | 実行ログ用モデル。`job_id`, `step`, `message`, `level`, `created_at` | `database/models/backfill_job_log.py` |
| 13 | database/models/__init__.py 更新 | 新モデル2つをインポート・エクスポート追加 | `database/models/__init__.py` |

### 1-2. マイグレーション・初期化

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 14 | Alembicマイグレーション生成 | `alembic revision --autogenerate -m "add_backfill_job_tables"` 実行 | `migrations/versions/` |
| 15 | マイグレーション内容確認 | 生成されたファイルの `upgrade()` に `create_table('backfill_jobs')` と `create_table('backfill_job_logs')` が含まれること確認 | `migrations/versions/xxxx_add_backfill_job_tables.py` |
| 16 | マイグレーション適用 | `alembic upgrade head` 実行してDBにテーブル作成 | — |
| 17 | テーブル作成確認 | `python -c "from database.models import BackfillJob, BackfillJobLog; print('OK')"` でimport確認 | — |
| 18 | 初期データ投入スクリプト雛形作成 | `scripts/seed_backfill_jobs.py` の雛形作成（中身は後で実装） | `scripts/seed_backfill_jobs.py` |

---

## Phase 2 — 日付範囲指定クロール機能の実装 (ステップ 19–30)

### 2-1. BaseCrawlerへの日付範囲機能追加

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 19 | BaseCrawlerに日付範囲パラメータ追加 | `__init__` に `start_date: Optional[date]`, `end_date: Optional[date]` を追加 | `crawler/base_crawler.py` |
| 20 | crawl_range メソッドの実装 | `crawl_range(start_date, end_date)` メソッドを追加。内部で `crawl_site` を呼びつつ日付フィルタ適用 | `crawler/base_crawler.py` |
| 21 | 日付フィルタ共通関数の作成 | `filter_by_date_range(items, start_date, end_date, date_field)` ユーティリティ関数作成 | `crawler/utils/date_filter.py` (新規) |
| 22 | 日付パース共通関数の作成 | 文字列から `date` オブジェクトへの変換関数 `parse_date_string(text)` 作成（和暦・西暦両対応） | `crawler/utils/date_parser.py` (新規) |
| 23 | ページネーション時の早期終了ロジック | 一覧ページで `start_date` より古い案件が出たら巡回打ち切りするロジック実装 | `crawler/base_crawler.py` |

### 2-2. GenericCrawlerへの統合

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 24 | GenericCrawlerに日付範囲対応追加 | `crawl_site` に `start_date`, `end_date` 引数追加、基底クラスの `crawl_range` を呼ぶよう修正 | `crawler/generic_crawler.py` |
| 25 | パーサーへの日付情報渡し | 詳細ページ解析時に `announcement_date` を抽出し、フィルタリングに使用できるようパーサー側で返す | `crawler/parsers/` 各パーサー |
| 26 | 設定駆動クローラへの日付範囲対応 | `ConfigDrivenCrawler` でも日付範囲指定巡回が動くよう修正 | `crawler/config_driven_crawler.py` |

### 2-3. GEPSCrawlerへの統合

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 27 | GEPSCrawlerの検索条件に日付追加 | `search_bids` メソッドに `start_date`, `end_date` パラメータ追加、GEPS検索フォームの日付項目に設定 | `crawler/geps_crawler.py` |
| 28 | GEPS検索結果の日付フィルタ | 検索結果一覧で公告日が範囲外ならスキップする処理追加 | `crawler/geps_crawler.py` |
| 29 | 詳細ページ取得時の日付確認 | 詳細ページの公告日を取得して範囲内か判定、外ならスキップ | `crawler/geps_crawler.py` |
| 30 | 統合テスト用ダミーデータ作成 | `tests/fixtures/backfill_sample.html` 作成、日付範囲フィルタのテスト用 | `tests/fixtures/backfill_sample.html` |

---

## Phase 3 — バックフィル実行サービスの実装 (ステップ 31–42)

### 3-1. BackfillService クラス作成

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 31 | BackfillServiceクラスの骨子作成 | `services/backfill_service.py` 新規作成。`__init__(session)`, `create_job()`, `run_job()` メソッド定義 | `services/backfill_service.py` |
| 32 | create_job メソッド実装 | 引数: `agency_id`, `years=2`。対象期間計算（今日 - years年 〜 今日）、`BackfillJob` レコード作成して返却 | `services/backfill_service.py` |
| 33 | run_job メソッド実装 | `job_id` 受取、ステータス running に更新、対象Agencyのクローラー種別判定、適切なクローラーで `crawl_range` 実行、結果をBid保存、件数カウント、ステータス done/failed 更新 | `services/backfill_service.py` |
| 34 | クローラー種別判定ロジック | Agencyの `system_type` または `BidSource.source_type` 見て `geps`/`web`/`pdf` 判定するヘルパー `_get_crawler_for_agency(agency_id)` 作成 | `services/backfill_service.py` |
| 35 | 進捗ログ記録機能 | `BackfillJobLog` に各ステップ（開始、各ページ処理、保存、完了/エラー）を記録する `_log(job_id, step, message, level)` メソッド追加 | `services/backfill_service.py` |
| 36 | エラーハンドリング・リトライ | 例外発生時は `error_message` に記録、ステータス failed、リトライ回数制限（最大3回）の仕組み追加 | `services/backfill_service.py` |

### 3-2. 既存機関へのバックフィルジョブ一括投入

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 37 | seed_backfill_jobs.py 実装 | `Agency` テーブルから `is_crawled=True` の全機関を取得、各機関に対して `BackfillService.create_job(years=2)` 実行 | `scripts/seed_backfill_jobs.py` |
| 38 | コマンドライン引数対応 | `--years`, `--agency-id`, `--category`, `--priority` 等のオプションで対象絞り込み可能にする | `scripts/seed_backfill_jobs.py` |
| 39 | 実行確認用ドライランモード | `--dry-run` で実際にジョブ作成せず対象件数のみ表示するモード追加 | `scripts/seed_backfill_jobs.py` |
| 40 | 重複ジョブ防止 | 同一 `agency_id` + 同一期間で `pending`/`running` のジョブが既にある場合はスキップするチェック追加 | `services/backfill_service.py` |
| 41 | 進捗表示機能 | `tqdm` 等で進捗バー表示、完了時にサマリー出力 | `scripts/seed_backfill_jobs.py` |
| 42 | 手動実行テスト | `python scripts/seed_backfill_jobs.py --dry-run` → `--agency-id 1 --years 1` で単一機関テスト実行 | — |

---

## Phase 4 — 重複排除・整合性修正 (ステップ 43–52)

### 4-1. 重複検出・排除ロジック

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 43 | 重複判定キーの最終確認 | `source_url` がユニークキーとして機能するか、複数ソースから同一案件取得時の挙動確認 | — |
| 44 | BidStorageServiceのupsert確認 | 既存 `save_bid()` が `source_url` ベースで upsert になっているか確認、なれば修正 | `services/bid_storage_service.py` |
| 45 | 重複排除サービス作成 | `services/backfill_dedup.py` 新規作成。`find_duplicates()`, `merge_duplicates()`, `clean_orphans()` メソッド実装 | `services/backfill_dedup.py` |
| 46 | 同一案件の複数ソース統合 | 複数の `BidSource` から同一 `source_url` が取得された場合、最初のものを正として他をスキップ | `services/backfill_dedup.py` |
| 47 | 過去データの価格補完ロジック | 既存レコードに `budget_amount` や `award_rate` が欠落していて、バックフィルで取得できた場合は上書き更新 | `services/backfill_dedup.py` |
| 48 | 整合性チェッククエリ作成 | `scripts/check_backfill_integrity.py` で重複件数、欠落フィールド件数、日付範囲外件数を集計 | `scripts/check_backfill_integrity.py` |

### 4-2. データ品質向上

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 49 | 欠落フィールド自動補完 | バックフィル取得データで `budget`, `deadline`, `qualifications` 等が埋まる場合の自動更新ロジック | `services/backfill_dedup.py` |
| 50 | 異常値検出・除外 | 予算額が0や異常に大きい、日付が未来すぎる等の異常値を検出してフラグ付け | `services/backfill_dedup.py` |
| 51 | 正規化処理の適用 | `BidNormalizer` をバックフィルデータにも適用（企業名正規化、業種分類等） | `services/bid_normalizer.py` 呼び出し追加 |
| 52 | 品質レポート生成 | バックフィル実行後に品質メトリクス（欠落率、重複率、補完率）を出力する `scripts/gen_backfill_quality_report.py` 作成 | `scripts/gen_backfill_quality_report.py` |

---

## Phase 5 — バックフィル進捗UI・管理画面 (ステップ 53–60)

### 5-1. 管理画面タブ追加

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 53 | app_admin.py にバックフィルタブ追加 | `st.tabs` に「バックフィル」タブ追加 | `app_admin.py` |
| 54 | ジョブ一覧表示 | `BackfillJob` を DataFrame で表示（機関名、期間、進捗、状態、件数、エラー） | `app_admin.py` |
| 55 | フィルタ・検索機能 | 状態、機関カテゴリ、期間でフィルタリング、機関名で検索 | `app_admin.py` |
| 56 | ジョブ詳細モーダル | 行クリックで詳細表示（ログ、エラー詳細、実行時間） | `app_admin.py` |
| 57 | 再実行ボタン | `failed`/`pending` ジョブに対して「再実行」ボタン配置、クリックで `BackfillService.run_job()` 呼び出し | `app_admin.py` |
| 58 | 新規ジョブ作成フォーム | 機関選択、期間指定、years指定で新規ジョブ作成フォーム追加 | `app_admin.py` |
| 59 | 一括操作機能 | チェックボックスで複数選択 → 「一括再実行」「一括キャンセル」 | `app_admin.py` |
| 60 | 進捗リアルタイム更新 | `st.rerun()` または WebSocket で実行中ジョブの進捗を自動更新 | `app_admin.py` |

---

## Phase 6 — 通知・スケジューラ統合 (ステップ 61–68)

### 6-1. 完了通知機能

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 61 | notifier.py にバックフィル通知追加 | `notify_backfill_done(job_id, agency_name, fetched_count, status)` 関数追加 | `notifier.py` |
| 62 | Slack通知テンプレート | 完了/失敗時のSlackメッセージフォーマット定義（機関名、期間、取得件数、所要時間、エラー有無） | `notifier.py` |
| 63 | LINE/メール通知テンプレート | 同様にLINE/メール用テンプレート追加 | `notifier.py` |
| 64 | 通知条件設定 | `SystemSetting` または専用テーブルで「完了時のみ」「失敗時のみ」「常に」を設定可能に | `database/models/system_setting.py` または新規 |

### 6-2. スケジューラ統合

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 65 | scheduler.py にバックフィルジョブ追加 | `add_backfill_job()` メソッド追加、デフォルト週1回（日曜深夜）実行 | `scheduler.py` |
| 66 | 実行済みジョブのスキップ機能 | `BackfillService.run_job()` 内で「直近7日以内に同一機関でdoneならスキップ」ロジック追加 | `services/backfill_service.py` |
| 67 | 手動トリガーポイント追加 | `crawler_task.py` に `execute_backfill(agency_id=None)` 関数追加、CLI/管理画面から呼び出し可能 | `crawler_task.py` |
| 68 | キューイング対応（RQ） | `BackfillService.run_job` を `@job` デコレータでRQタスク化、スケジューラからキュー投入 | `services/backfill_service.py`, `scheduler.py` |

---

## Phase 7 — テスト・ドキュメント・最終確認 (ステップ 69–72)

### 7-1. テスト作成

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 69 | BackfillService単体テスト | `tests/test_backfill_service.py` 作成。モッククローラーで `create_job`/`run_job` の正常系・異常系テスト | `tests/test_backfill_service.py` |
| 70 | 重複排除テスト | `tests/test_backfill_dedup.py` 作成。同一source_urlの複数データでupsert動作確認 | `tests/test_backfill_dedup.py` |
| 71 | 日付範囲フィルタテスト | `tests/test_date_range_crawl.py` 作成。過去/未来/範囲内のダミーデータでフィルタ動作確認 | `tests/test_date_range_crawl.py` |

### 7-2. 結合テスト・ドキュメント

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 72 | 全体結合テスト・運用マニュアル作成 | `tests/test_backfill_pipeline.py` でインベントリ登録→ジョブ作成→実行→重複排除→通知の一連を検証。`運用マニュアル_バックフィル.md` 作成（手動運用手順、トラブルシューティング、再実行手順） | `tests/test_backfill_pipeline.py`, `運用マニュアル_バックフィル.md` |

---

## 前提条件チェック（各Phase開始前に実施）

```
[ ] Python 3.14 が `python --version` で確認可能
[ ] `pip install -r requirements.txt` がエラーなく完了
[ ] Playwright browsers が `playwright install` でインストール済み
[ ] 既存クローラー（GEPS、Generic）が正常動作すること確認済み
[ ] `.env` ファイルが存在し、 GEMINI_API_KEY 等が設定済み
[ ] `alembic current` でマイグレーション状態確認
[ ] `python -c "from database.models import BackfillJob; print('OK')"` が成功（Phase 1完了後）
```

---

## Phase 別の優先度と工数目安

| Phase | 内容 | 優先度 | 工数目安 |
|-------|------|--------|----------|
| Phase 0 | 事前調査・設計 | 高 | 3日 |
| Phase 1 | バックフィルジョブモデル | 高 | 1週間 |
| Phase 2 | 日付範囲指定クロール | 高 | 2週間 |
| Phase 3 | バックフィル実行サービス | 高 | 2週間 |
| Phase 4 | 重複排除・整合性修正 | 中 | 1週間 |
| Phase 5 | 管理画面UI | 中 | 1週間 |
| Phase 6 | 通知・スケジューラ統合 | 中 | 1週間 |
| Phase 7 | テスト・ドキュメント | 低 | 3日 |

---

## 成功基準

- [ ] 任意の発注機関について、指定期間（例：過去2年）の入札情報を一括取得可能
- [ ] 取得データが `source_url` ベースで重複排除され、既存データと統合される
- [ ] 欠落していた予算額・締切日・参加資格等がバックフィルで補完される
- [ ] 管理画面でジョブの進捗・履歴・エラーが確認可能
- [ ] 完了/失敗時に Slack/LINE/メールで通知される
- [ ] スケジューラで定期実行（週1回等）が自動動作する
- [ ] 手動トリガーで任意の機関・期間を再実行可能

---

## テスト・レビューチェックリスト

- [ ] 各ステップ完了後にマイグレーション適用（`alembic upgrade head`）
- [ ] ユニットテスト作成（`tests/` 配下）
- [ ] `python -m py_compile` で構文チェック
- [ ] `mypy` 型チェック実行
- [ ] エラーログ出力確認
- [ ] 手動結合テスト（ステップ72）
- [ ] 本番環境での単一機関・短期間テスト（ステップ42相当）

---

*本計画は低性能LLMでも実装できるよう、各ステップを「単一ファイル・単一関数」レベルまで細分化しています。ステップ完了ごとにコミットし、CIで検証しながら進めることを推奨します。*