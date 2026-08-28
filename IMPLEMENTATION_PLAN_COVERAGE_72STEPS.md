# データ網羅性・精度向上 72ステップ実装計画

## 前提条件と全体構成

- **対象プロジェクト**: `/home/herbmatsui/入札システム`
- **DB**: `bids_system.db`（SQLite、SQLAlchemy ORM）+ 既存 `bids.db`
- **既存クローラ**: `crawler/geps_crawler.py`, `url_hunter.py`, `rule_generator.py`, `crawler_task.py`
- **既存サービス**: `config.py`, `db_manager.py`, `scheduler.py`(APScheduler), `notifier.py`
- **既存UI**: `app_admin.py`, `app_dashboard.py`, `app_observability.py`, `app_mobile.py`
- **OCR**: `ocr/` 配下（PDFテキスト抽出パイプライン）
- **マイグレーション**: Alembic（`migrations/versions/`）
- **目標**: NJSS相当の発注機関網羅（9,056機関）に向け、未対応都道府県・市町村の追加とPDF/HTML両形式の人手チェック工程を確立

---

## フェーズ概要

| フェーズ | 対象項目 | ステップ | 概要 |
|---------|---------|---------|------|
| 第1フェーズ | 項目1 | 1-8 | 都道府県別クローラー優先度マトリクス |
| 第2フェーズ | 項目2 | 9-16 | 市町村単位の発注機関インベントリ |
| 第3フェーズ | 項目3 | 17-24 | クローラーテンプレート化・共通基盤 |
| 第4フェーズ | 項目4 | 25-32 | PDF/HTML形式別パーサーのモジュール化 |
| 第5フェーズ | 項目5 | 33-40 | 人手チェック工程の運用フロー |
| 第6フェーズ | 項目6 | 41-48 | 品質メトリクス可視化・アラート |
| 第7フェーズ | 項目7 | 49-56 | 過去データ遡及取得・バックフィル |
| 第8フェーズ | 項目8 | 57-64 | クローラー健全性自動テスト・CI |
| 第9フェーズ | 項目9 | 65-72 | 運用コスト削減の優先度付けアルゴリズム |

---

## 第1フェーズ: 都道府県別クローラー優先度マトリクス（ステップ1-8）

### ステップ1: 優先度評価用モデル作成
- ファイル: `database/models/crawl_priority.py` 新規作成
- カラム:
  - `id`: 主キー（Integer, autoincrement）
  - `prefecture_code`: 都道府県コード（String(2), index=True）
  - `prefecture_name`: 都道府県名（String(32)）
  - `agency_count`: 推定発注機関数（Integer, default=0）
  - `target_industry_match`: 自社対象業種と一致度（Float, default=0.0）
  - `score`: 優先度スコア（Float, default=0.0）
  - `status`: 状態（String(16), default="pending"）← pending/active/done
  - `created_at`, `updated_at`: 日時

### ステップ2: 都道府県マスタ定数ファイル作成
- ファイル: `config/prefectures.py` 新規作成
- 47都道府県＋国外のコード・名前辞書を定義:
  ```python
  PREFECTURES = {
      "01": "北海道", "02": "青森県", "03": "岩手県", ... "47": "沖縄県",
  }
  ```

### ステップ3: 優先度スコア算出関数作成
- ファイル: `services/priority_scorer.py` 新規作成
- 関数:
  - `calc_score(agency_count, industry_match)`: `agency_count * 0.6 + industry_match * 0.4` を100点満点に正規化
  - `rank_prefectures(rows)`: スコア降順でソート

### ステップ4: 既存クロール実績から機関数を集計
- ファイル: `scripts/count_agencies_by_pref.py` 新規作成
- 既存 `bids_system.db` の `bids` テーブルから `prefecture` ごとに発注機関数を COUNT
- 結果を `crawl_priority.agency_count` に保存

### ステップ5: 自社対象業種マッピング設定
- ファイル: `config/target_industries.py` 新規作成
- 自社が入札に関心を持つ業種キーワードリストを定義:
  ```python
  TARGET_INDUSTRIES = ["清掃", "警備", "派遣", "情報通信", "調査", "建設"]
  ```

### ステップ6: 業種一致度算出スクリプト
- ファイル: `scripts/score_industry_match.py` 新規作成
- 各都道府県の既存案件タイトルと `TARGET_INDUSTRIES` を突合
- 一致率を `crawl_priority.target_industry_match` に保存

### ステップ7: 優先度マトリクス集計スクリプト
- ファイル: `scripts/build_priority_matrix.py` 新規作成
- ステップ4・6の値を読み込み、`priority_scorer.calc_score` で `score` を算出
- 上位から `status="active"` を付与（初回は北海道・東北・四国・九州を優先）

### ステップ8: 優先度マトリクス表示UI
- ファイル: `app_admin.py` に「優先度マトリクス」タブ追加
- DataFrameで都道府県・機関数・業種一致度・スコア・状態を表示
- `st.dataframe()` で描画

---

## 第2フェーズ: 市町村単位の発注機関インベントリ（ステップ9-16）

### ステップ9: 発注機関インベントリモデル作成
- ファイル: `database/models/agency_inventory.py` 新規作成
- カラム:
  - `id`: 主キー
  - `agency_name`: 発注機関名（String(255), index=True）
  - `prefecture_code`: 都道府県コード（String(2)）
  - `municipality`: 市区町村名（String(128), nullable）
  - `top_page_url`: トップページURL（String(1024), nullable）
  - `bid_page_url`: 入札情報ページURL（String(1024), nullable）
  - `page_format`: 形式（String(16)）← html/pdf/mixed/unknown
  - `is_crawled`: クロール済フラグ（Boolean, default=False）
  - `crawler_config_id`: 紐付け設定ID（Integer, nullable）
  - `created_at`, `updated_at`: 日時

### ステップ10: 総合行政ネットワーク(LASDEC)URL定数
- ファイル: `config/agency_sources.py` 新規作成
- 都道府県・政令市の公式ポータルURL辞書を定義
- 例: `{"北海道": "https://www.pref.hokkaido.lg.jp/", ...}`

### ステップ11: 機関リスト取得用スクレイパ基底
- ファイル: `crawler/agency_list_fetcher.py` 新規作成
- クラス: `AgencyListFetcher`
- メソッド:
  - `fetch_top_page(url)`: トップページHTML取得
  - `find_bid_links(html)`: 「入札」「公募」「調達」リンクを抽出

### ステップ12: 都道府県庁クロール用実装
- ファイル: `crawler/agency_lists/prefecture_fetcher.py` 新規作成
- `AgencyListFetcher` を継承し、47都道府県庁の入札ページを探索
- 見つけたURLを `agency_inventory` に upsert

### ステップ13: 政令市・市区町村クロール用実装
- ファイル: `crawler/agency_lists/municipality_fetcher.py` 新規作成
- 市区町村ポータルから入札ページを探索
- 対象を `prefecture_code` で絞り込して実行

### ステップ14: インベントリ登録リポジトリ作成
- ファイル: `repositories/agency_inventory_repository.py` 新規作成
- メソッド:
  - `upsert(agency_name, prefecture_code, bid_page_url)`: 重複排除で登録
  - `list_uncrawled(limit)`: 未クロール機関一覧
  - `mark_crawled(agency_id)`: フラグ更新

### ステップ15: インベントリ初期投入スクリプト
- ファイル: `scripts/seed_agency_inventory.py` 新規作成
- ステップ12・13のフェッチャを呼び出し、結果をDBへ一括投入
- 実行: `python scripts/seed_agency_inventory.py --pref 01`

### ステップ16: インベントリ管理UI
- ファイル: `app_admin.py` に「発注機関インベントリ」タブ追加
- 都道府県別の機関数・クロール率を表示
- 未クロール機関の一覧と「クロール実行」ボタン

---

## 第3フェーズ: クローラーテンプレート化・共通基盤（ステップ17-24）

### ステップ17: クローラ基底クラス定義
- ファイル: `crawler/base_crawler.py` 新規作成
- クラス: `BaseCrawler`
- 共通メソッド:
  - `fetch(url, retry=3)`: HTTP取得＋リトライ
  - `parse_list(html)`: 一覧ページ解析（抽象）
  - `parse_detail(html)`: 詳細ページ解析（抽象）
  - `save(items)`: リポジトリへ保存

### ステップ18: 既存geps_crawlerの基底統合
- ファイル: `crawler/geps_crawler.py` を更新
- `BaseCrawler` を継承するようクラス宣言を変更
- 重複していた `fetch` 等を基底へ移動

### ステップ19: 機関別設定YAMLスキーマ定義
- ファイル: `config/crawler_schema.yaml` 新規作成
- 各機関の設定項目を定義:
  ```yaml
  agency:
    name: "示例市役所"
    list_url: "https://..."
    list_selector: ".bid-list a"
    detail_selector: ".detail"
    page_format: html
  ```

### ステップ20: 設定駆動クローラ実装
- ファイル: `crawler/config_driven_crawler.py` 新規作成
- クラス: `ConfigDrivenCrawler(BaseCrawler)`
- YAML設定からセレクタ等を読み込み、新規機関をコード不要で対応

### ステップ21: 共通ページネーション処理
- ファイル: `crawler/pagination.py` 新規作成
- 関数:
  - `find_next_page(html, base_url)`: 次ページリンク抽出
  - `crawl_all_pages(start_url, parse_fn)`: 全ページ巡回ジェネレータ

### ステップ22: 共通エラーハンドリング追加
- ファイル: `crawler/exceptions.py` を更新（既存 `exceptions.py` を拡張）
- `CrawlError`, `ParseError`, `RateLimitError` を定義
- 基底クラスの `fetch` で捕捉してログ出力

### ステップ23: 新規機関追加用ボイラープレート生成
- ファイル: `scripts/gen_crawler.py` 新規作成
- `python scripts/gen_crawler.py --name "示例市" --url "https://..."` で
- YAML設定ファイルと雛形を自動生成

### ステップ24: 設定駆動クローラのテスト
- ファイル: `tests/test_config_driven_crawler.py` 新規作成
- ダミーHTMLで `parse_list`/`parse_detail` を検証
- `tests/fixtures/sample_list.html` を作成

---

## 第4フェーズ: PDF/HTML形式別パーサーのモジュール化（ステップ25-32）

### ステップ25: パーサー基底インターフェース定義
- ファイル: `crawler/parsers/base_parser.py` 新規作成
- クラス: `BaseParser`
- メソッド: `extract_fields(raw_text) -> dict`（抽象）

### ステップ26: HTMLパーサー実装
- ファイル: `crawler/parsers/html_parser.py` 新規作成
- BeautifulSoupを用いて案件名・予定価格・締切日を抽出
- セレクタは `crawler_schema.yaml` から取得

### ステップ27: PDFパーサー実装（OCR連携）
- ファイル: `crawler/parsers/pdf_parser.py` 新規作成
- 既存 `ocr/` の `PDFPipeline` を呼び出しテキスト抽出
- 抽出テキストを `rule_generator.py` のルールで構造化

### ステップ28: 金額・日付正規化ユーティリティ
- ファイル: `crawler/parsers/field_normalizer.py` 新規作成
- 関数:
  - `normalize_amount(text)`: 「1,234,567円」→ 1234567
  - `normalize_date(text)`: 「2026.08.27」→ date(2026,8,27)
  - `normalize_agency(text)`: 機関名の全角半角統一

### ステップ29: 形式判定ロジック
- ファイル: `crawler/parsers/format_detector.py` 新規作成
- 関数: `detect_format(url, content_type) -> "html"|"pdf"|"mixed"`
- リンク先の拡張子・Content-Typeで判定

### ステップ30: ルールジェネレータ拡張
- ファイル: `rule_generator.py` を更新
- PDF/HTML共通の抽出ルールをYAML化
- `generate_rule(html_or_text)` で新規機関のルール自動提案

### ステップ31: パーサー選択ディスパッチャ
- ファイル: `crawler/parsers/parser_dispatcher.py` 新規作成
- 関数: `dispatch(format, raw) -> dict`
- 形式に応じ `HtmlParser` / `PdfParser` を呼び分け

### ステップ32: パーサー統合テスト
- ファイル: `tests/test_parsers.py` 新規作成
- HTML/PDFサンプル各2件で正規化結果を検証
- `tests/fixtures/sample.pdf`, `sample.html` を用意

---

## 第5フェーズ: 人手チェック工程の運用フロー（ステップ33-40）

### ステップ33: 人手チェック用モデル作成
- ファイル: `database/models/qa_review.py` 新規作成
- カラム:
  - `id`: 主キー
  - `bid_id`: 対象案件ID（Integer, FK）
  - `reviewer`: 確認担当者（String(64), nullable）
  - `status`: 状態（String(16)）← pending/reviewing/approved/rejected
  - `note`: 修正メモ（Text, nullable）
  - `reviewed_at`: 確認日時（DateTime, nullable）
  - `created_at`: 作成日時

### ステップ34: 日次差分抽出バッチ
- ファイル: `scripts/extract_qa_targets.py` 新規作成
- 前日クロール分のうち「必須項目欠落」または「低信頼度」を `qa_review` に登録
- `status="pending"` で新規作成

### ステップ35: 確認担当者割当サービス
- ファイル: `services/qa_assignment_service.py` 新規作成
- メソッド:
  - `assign_reviewer(review_id, reviewer)`: 担当者割当
  - `auto_balance()`: 負荷平準化で未割当を振り分け

### ステップ36: 修正反映パイプライン
- ファイル: `services/qa_fix_pipeline.py` 新規作成
- メソッド:
  - `apply_fix(bid_id, corrected_fields)`: 承認時に `bids` を更新
  - `reject(bid_id, reason)`: 除外・要再取得フラグ

### ステップ37: 管理画面の確認ワークフローUI
- ファイル: `app_admin.py` に「人手チェック」タブ追加
- 未確認一覧（案件名・機関・信頼度）を表示
- 詳細画面で「承認」「修正」「除外」ボタン

### ステップ38: 修正入力フォームUI
- ファイル: `services/qa_review_page.py` 新規作成
- 関数: `render_review_detail(review_id)`
- 項目ごとに `st.text_input` で修正値入力

### ステップ39: 確認進捗ダッシュボード
- ファイル: `app_observability.py` に「QA進捗」メトリクス追加
- 未確認件数・承認率・担当者別負荷を表示

### ステップ40: 人手チェック運用スクリプト結合
- ファイル: `scheduler.py` に日次ジョブ追加
- `extract_qa_targets` → `auto_balance` を毎朝実行
- `app_admin.py` で手動トリガーも可能に

---

## 第6フェーズ: 品質メトリクス可視化・アラート（ステップ41-48）

### ステップ41: 品質メトリクス集計サービス
- ファイル: `services/quality_metrics_service.py` 新規作成
- メソッド:
  - `count_missing_fields()`: 必須項目欠落率
  - `count_duplicates()`: 重複率
  - `coverage_rate()`: インベントリ対比クロール率
  - `daily_delta()`: 前日比変動

### ステップ42: メトリクス保存モデル
- ファイル: `database/models/quality_metric.py` 新規作成
- カラム: `id`, `metric_name`, `value`, `recorded_at`
- 日次バッチで `quality_metrics_service` の結果を保存

### ステップ43: 閾値設定モデル
- ファイル: `database/models/quality_threshold.py` 新規作成
- カラム: `id`, `metric_name`, `warn_at`, `alert_at`
- デフォルト: 欠落率 warn=5%, alert=15%

### ステップ44: アラート評価サービス
- ファイル: `services/quality_alert_service.py` 新規作成
- メソッド: `evaluate(metric_name, value)` → warn/alert/ok を返却
- 既存 `notifier.py` の `send_slack`/`send_mail` を呼び出し

### ステップ45: アラート通知テンプレート
- ファイル: `notifier.py` を更新
- `notify_quality_issue(metric_name, value, level)` を追加
- Slack/メール用フォーマットを定義

### ステップ46: 品質ダッシュボードUI
- ファイル: `app_observability.py` に「データ品質」タブ追加
- メトリクスを時系列グラフ（Plotly）で表示
- 閾値超過は赤色強調

### ステップ47: メトリクス集計バッチ
- ファイル: `scripts/collect_quality_metrics.py` 新規作成
- 日次で `quality_metrics_service` を実行しDB保存＋アラート評価

### ステップ48: 品質メトリクステスト
- ファイル: `tests/test_quality_metrics.py` 新規作成
- ダミーデータで欠落率・重複率・アラート判定を検証

---

## 第7フェーズ: 過去データ遡及取得・バックフィル（ステップ49-56）

### ステップ49: バックフィル用ジョブモデル
- ファイル: `database/models/backfill_job.py` 新規作成
- カラム:
  - `id`, `agency_id`, `start_date`, `end_date`
  - `status`: pending/running/done/failed
  - `fetched_count`, `error_message`, `created_at`

### ステップ50: 日付範囲指定クロール機能
- ファイル: `crawler/base_crawler.py` を更新
- `crawl_range(start_date, end_date)` メソッド追加
- 一覧ページの公告日でフィルタリング

### ステップ51: バックフィル実行サービス
- ファイル: `services/backfill_service.py` 新規作成
- メソッド:
  - `create_job(agency_id, years=2)`: 過去2年分ジョブ作成
  - `run_job(job_id)`: `crawl_range` で一括取得

### ステップ52: 既存機関のバックフィル投入
- ファイル: `scripts/seed_backfill_jobs.py` 新規作成
- `agency_inventory` の全機関に対して `backfill_service.create_job` を実行

### ステップ53: バックフィル進捗UI
- ファイル: `app_admin.py` に「バックフィル」タブ追加
- ジョブ一覧（機関・期間・進捗・状態）を表示
- 再実行ボタンを用意

### ステップ54: 重複排除・整合性修正
- ファイル: `services/backfill_dedup.py` 新規作成
- `source_url` で重複を検出し、`upsert` で統合
- 過去データの予定価格・落札価格を補完

### ステップ55: バックフィル完了通知
- ファイル: `notifier.py` を更新
- `notify_backfill_done(job_id, count)` を追加
- ジョブ完了時にSlack/メール通知

### ステップ56: バックフィル結合テスト
- ファイル: `tests/test_backfill.py` 新規作成
- 1機関・過去1ヶ月で動作検証
- 重複排除の結果を確認

---

## 第8フェーズ: クローラー健全性自動テスト・CI（ステップ57-64）

### ステップ57: 機関別スモークテスト雛形
- ファイル: `tests/test_crawler_smoke.py` 新規作成
- 主要機関のサンプルURLで `ConfigDrivenCrawler` が動くか検証

### ステップ58: 構造変更検知テスト
- ファイル: `tests/test_structure_change.py` 新規作成
- 既存セレクタで `parse_list` が0件を返す場合に失敗するアサーション

### ステップ59: テスト用フィクスチャ更新
- ファイル: `tests/fixtures/` に各機関のHTML/PDFサンプルを格納
- `sample_list.html`, `sample_detail.html`, `sample.pdf` を追加

### ステップ60: 構造変更検知の自動通知
- ファイル: `services/crawler_health_service.py` 新規作成
- テスト失敗時に `notifier.notify_structure_change(agency, error)` を呼ぶ

### ステップ61: GitHub Actionsワークフロー作成
- ファイル: `.github/workflows/crawler-ci.yml` 新規作成
- 内容:
  - `pip install -r requirements.txt`
  - `python -m pytest tests/test_crawler_smoke.py tests/test_structure_change.py`
  - 失敗時にSlack通知

### ステップ62: ローカル事前チェックスクリプト
- ファイル: `scripts/precommit_crawl_check.py` 新規作成
- git pre-commitフックから呼び出し
- クローラ関連ファイル変更時にスモークテスト実行

### ステップ63: 定期健全性監視ジョブ
- ファイル: `scheduler.py` に追加
- 週1回 `test_structure_change` 相当のチェックを本番URLで実行
- 異常時は `crawler_health_service` 経由で通知

### ステップ64: CI/テスト結合レポート
- ファイル: `scripts/gen_crawler_health_report.py` 新規作成
- 各機関の最終成功日時・失敗回数を集計しMarkdown出力

---

## 第9フェーズ: 運用コスト削減の優先度付けアルゴリズム（ステップ65-72）

### ステップ65: 運用コストモデル作成
- ファイル: `database/models/op_cost.py` 新規作成
- カラム:
  - `id`, `agency_id`
  - `crawl_frequency`: 頻度（String(8)）← daily/weekly/monthly
  - `last_value_score`: 直近価値スコア（Float）
  - `cost_score`: 取得コストスコア（Float）
  - `updated_at`

### ステップ66: 価値スコア算出関数
- ファイル: `services/value_scorer.py` 新規作成
- 関数:
  - `calc_value(agency)`: 自社受注実績相関・競合度・鮮度から価値を算出
  - `calc_cost(agency)`: ページ数・PDF比率・構造複雑度からコストを算出

### ステップ67: 頻度最適化アルゴリズム
- ファイル: `services/frequency_optimizer.py` 新規作成
- メソッド: `optimize(agency)` → value/cost 比で daily/weekly/monthly を決定
- 人手チェックリソースも `qa_review` 件数で加重

### ステップ68: 最適化バッチ適用
- ファイル: `scripts/apply_frequency_optimization.py` 新規作成
- 全機関に対して `frequency_optimizer.optimize` を実行
- 結果を `op_cost` に保存し `CrawlConfig` の頻度を更新

### ステップ69: リソース配分可視化UI
- ファイル: `app_observability.py` に「運用最適化」タブ追加
- 機関×頻度のヒートマップとコスト/価値散布図を表示

### ステップ70: 優先度付けルール設定UI
- ファイル: `app_admin.py` に「最適化ルール」タブ追加
- 価値係数・コスト係数を管理者が調整可能に

### ステップ71: 最適化効果レポート
- ファイル: `scripts/gen_optimization_report.py` 新規作成
- 適用前後でクロール総数・人手チェック件数・カバー率を比較出力

### ステップ72: 全体結合テストと運用マニュアル
- ファイル: `tests/test_coverage_pipeline.py` 新規作成
- インベントリ登録→クロール→人手チェック→バックフィル→最適化の一連を検証
- `運用マニュアル.md` を作成（手動運用手順を記載）

---

## 実装順序の要約

| 優先度 | ステップ | 内容 | 主要ファイル |
|--------|---------|------|---------|
| 1 | 1-8 | 優先度マトリクス | `services/priority_scorer.py` |
| 2 | 9-16 | 発注機関インベントリ | `database/models/agency_inventory.py` |
| 3 | 17-24 | クローラ共通基盤 | `crawler/base_crawler.py` |
| 4 | 25-32 | PDF/HTMLパーサー | `crawler/parsers/` |
| 5 | 33-40 | 人手チェック運用 | `services/qa_*.py` |
| 6 | 41-48 | 品質メトリクス | `services/quality_metrics_service.py` |
| 7 | 49-56 | バックフィル | `services/backfill_service.py` |
| 8 | 57-64 | テスト・CI | `.github/workflows/crawler-ci.yml` |
| 9 | 65-72 | 最適化アルゴリズム | `services/frequency_optimizer.py` |

## テスト・レビューチェックリスト

- [ ] 各ステップ完了後にマイグレーション適用（`alembic upgrade head`）
- [ ] ユニットテスト作成（`tests/` 配下）
- [ ] `python -m py_compile` で構文チェック
- [ ] `mypy` 型チェック実行
- [ ] エラーログ出力確認
- [ ] 手動結合テスト（ステップ72）
- [ ] 本番URLでのスモークテスト（ステップ57）

---

*本計画は低性能LLMでも実装できるよう、各ステップを「単一ファイル・単一関数」レベルまで細分化しています。ステップ完了ごとにコミットし、CIで検証しながら進めることを推奨します。*
