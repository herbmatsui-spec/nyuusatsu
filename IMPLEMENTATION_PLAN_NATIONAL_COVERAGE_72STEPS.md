# 全国入札情報巡回システム — 全国網羅化 72ステップ実装計画書

> **目標**: 現在の特定サイト（GEPS、愛媛県等）から、全国47都道府県、主要市区町村，全省庁の入札サイトに対応した共通クローラ基盤を構築する。あわせて発注機関を「国」「都道府県」「市区町村」「外郭団体」のカテゴリでフィルタリング可能にする。
> **前提**: Python 3.14, SQLite, Playwright/Chromium導入済み, Redis 3.0+, 既存コードベース（geps_crawler.py, base_crawler.py等）

---

## Phase 0 — 現状分析・設計 (ステップ 1–8)

### 0-1. 現状コードベース調査

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 1 | 既存クローラ構造の総取っ替え | `geps_crawler.py`, `base_crawler.py`, `generic_crawler.py` のクラス構造・メソッド一覧を作成 | — |
| 2 | 既存AgencyConfigのフォーマット確認 | `crawler/parsers/agency_config/ehime.json` のフィールド構成を確認 | `crawler/parsers/agency_config/ehime.json` |
| 3 | 既存DBモデルの確認 | `database/models/` の `Agency`, `CrawlConfig`, `Bid` 等のテーブル定義を確認 | `database/models/__init__.py` |
| 4 | 既存パイプラインの接続確認 | `crawler/pipeline.py` の `crawl_agency_task`, `trigger_agency_crawl` の連携を確認 | `crawler/pipeline.py` |
| 5 | キュー・タスク定義の確認 | `queue/tasks/crawl_tasks.py` 等のタスク定義を確認 | `queue/tasks/crawl_tasks.py` |
| 6 | ベースURL registryの現状確認 | 既にUrlHunter等のURL収集機能があるか確認 | `crawler/` |
| 7 | ログ出力形式の統一化確認 | 既存ロガーがどの形式（JSON/テキスト）を使用しているか確認 | 全ソース |
| 8 | テストカバレッジの確認 | `tests/` の既存テストケース总数とカバレッジを確認 | `tests/` |

---

## Phase 1 — 発注機関カテゴリ分類データベースの構築 (ステップ 9–20)

### 1-1. データモデルの設計

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 9 | AgencyCategoryモデルの作成 | `database/models/agency_category.py` に `id`, `name`, `description`, `priority` フィールドを定義 | `database/models/agency_category.py` |
| 10 | Agencyモデルの拡張 | 既存の `Agency` モデルに `category_id` (FK), `code` (全国地方公共団体コード), `priority_level` (高/中/低) フィールドを追加 | `database/models/agency.py` |
| 11 | マイグレーションファイルの作成 | `alembic/` に `add_agency_category_table` と `add_agency_fields` のマイグレーションを作成 | `migrations/versions/` |
| 12 | カテゴリ初期データ投入スクリプト | 「国」「都道府県」「市区町村」「外郭団体」の4カテゴリをINSERT | `scripts/init_categories.py` |

### 1-2. 省政府庁マスタデータの整備

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 13 | 省政府庁マスタCSVの作成 | 全省庁（例：財務省、厚生労働省等）の名前をCSVにまとめる | `data/ministries.csv` |
| 14 | 省政府庁のDBへの一括投入 | `scripts/import_ministries.py` でCSVからAgency（category_id=国）を一括INSERT | `scripts/import_ministries.py` |
| 15 | GEPS URLパターン確認 | GEPSの全省庁一覧ページからURLパターンを確認 | `geps_crawler.py` |

### 1-3. 都道府県マスタデータの整備

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 16 | 都道府県マスタCSVの作成 | 47都道府県の名前と全国地方公共団体コード（2桁）をCSVにまとめる | `data/prefectures.csv` |
| 17 | 都道府県URLパターン調査 | 各都道府県の入札情報サイトのURLパターンを調査（例：`https://www.pref.ehime.jp/bid/`） | — |
| 18 | 都道府県のDBへの一括投入 | `scripts/import_prefectures.py` でCSVからAgency（category_id=都道府県）を一括INSERT | `scripts/import_prefectures.py` |
| 19 | 全市区町村コードリストの準備 | 全国地方公共団体コード（6桁）の全集をCSVで準備（総務省公開データ 활용） | `data/municipalities.csv` |
| 20 | カテゴリ別集計クエリの作成 | `scripts/report_by_category.py` でカテゴリ別のAgency件数・Bid件数を集計 | `scripts/report_by_category.py` |

---

## Phase 2 — 共通クローラ基盤の拡張 (ステップ 21–34)

### 2-1. BaseCrawlerの拡張

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 21 | BaseCrawlerにカテゴリフィルタ追加 | `BaseCrawler.__init__` に `categories: List[str]` パラメータを追加し、対象カテゴリを制限 | `crawler/base_crawler.py` |
| 22 | BaseCrawlerに優先度フィルタ追加 | `BaseCrawler` に `priority_levels: List[str]` パラメータを追加（高/中/低） | `crawler/base_crawler.py` |
| 23 | 共通リンク抽出メソッドの実装 | `BaseCrawler.extract_links()` を強化し、テーブル・リスト・グリッド等の多様なHTML構造に対応 | `crawler/base_crawler.py` |
| 24 | ページネーション自動検出の実装 | 「次へ」「下一页」等のページ遷移リンクを自動検出する `detect_pagination()` を追加 | `crawler/base_crawler.py` |
| 25 | 動的コンテンツ待機策略の拡張 | `BaseCrawler` に `ContentWaitStrategy` クラスを追加（networkidle, domcontentloaded, selector等） | `crawler/base_crawler.py` |

### 2-2. サイト構造自動検出機能

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 26 | HTMLパターン検出クラスの作成 | `crawler/parsers/structure_detector.py` にテーブル構造・リスト構造・カード構造を検出するクラスを実装 | `crawler/parsers/structure_detector.py` |
| 27 | XPath/CSSセレクタ自動生成功能 | 検出したHTML構造から最適なCSSセレクタを自動生成する `SelectorGenerator` を追加 | `crawler/parsers/selector_generator.py` |
| 28 | 構造変更検知功能的追加 | 以前成功したセレクタで抽出失敗した場合にアラートを出す `StructureChangeDetector` を追加 | `crawler/parsers/structure_change_detector.py` |
| 29 | フォールバック戦略の実装 | 優先セレクタ失敗時に代替セレクタを試す `FallbackSelectorStrategy` を追加 | `crawler/parsers/fallback_selector.py` |

### 2-3. GenericCrawlerの改良

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 30 | GenericCrawlerのカテゴリ対応 | `GenericCrawler` を拡張し、Agencyのカテゴリに基づく巡回対象絞り込みに対応 | `crawler/generic_crawler.py` |
| 31 | GenericCrawlerの優先度対応 | 優先度（高/中/低）に基づく巡回頻度の調整機能を追加 | `crawler/generic_crawler.py` |
| 32 | 巡回結果へのカテゴリ情報付加 | クローラ結果がどのカテゴリから取得されたかを記録 | `crawler/generic_crawler.py` |
| 33 | 共通エラーハンドリングの追加 | BaseCrawlerに全クローラ通用的エラー処理（タイムアウト、SSLエラー、認証エラー等）を実装 | `crawler/base_crawler.py` |
| 34 | ロガーの統一化 | 全クローラで統一されたJSONログ形式を使用するよう修正 | `crawler/base_crawler.py` |

---

## Phase 3 — 全国地方公共団体コード対応URLレジストリの作成 (ステップ 35–46)

### 3-1. URLレジストリ基盤の構築

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 35 | URLレジストريكライスの作成 | `crawler/registry/__init__.py` にレジストリ基底クラスを作成 | `crawler/registry/__init__.py` |
| 36 | PrefectureRegistryクラスの作成 | 47都道府県の入札情報URLを管理する `PrefectureRegistry` を実装 | `crawler/registry/prefecture_registry.py` |
| 37 | CityRegistryクラスの作成 | 主要市区町村の入札情報URLを管理する `CityRegistry` を実装 | `crawler/registry/city_registry.py` |
| 38 | MunicipalityRegistryクラスの作成 | 全市区町村（1700+）のURLを管理する `MunicipalityRegistry` を実装 | `crawler/registry/municipality_registry.py` |
| 39 | URL_VALIDITY_CHECKの追加 | 各URLのアクセス可否を定期確認し、無効URLをスキップする機能を追加 | `crawler/registry/url_validator.py` |

### 3-2. URLパターンの調査・登録

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 40 | 都道府県URLパターン集的 | 47都道府県の中央府省庁 Procurement 页のURLを集約 | `data/prefecture_urls.csv` |
| 41 | 市区町村URLパターン調査 | 人口上位100市区町村の入札情報URLを手動調査 | `data/city_urls.csv` |
| 42 | URLテンプレートシステムの作成 | URLパターンを正規表現で定義し、コードから動的URL生成 | `crawler/registry/url_template.py` |
| 43 | URL変更検知・自動通知機能 | 登録URLが404等になった場合に管理者へ通知する機能を追加 | `crawler/registry/url_change_detector.py` |

### 3-3. レジストリのDB統合

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 44 | AgencyテーブルへのURL登録 | 既存の `Agency` テーブルに `base_url`, `bid_url_pattern` フィールドを追加 | `database/models/agency.py` |
| 45 | マイグレーションファイルの作成 | URL関連フィールド追加のマイグレーションを作成 | `migrations/versions/` |
| 46 | レジストリ → DB同期スクリプト | `scripts/sync_registry_to_db.py` でレジストリのURLをAgencyテーブルに同期 | `scripts/sync_registry_to_db.py` |

---

## Phase 4 — 省政府庁（GEPS等）クローラの拡張 (ステップ 47–54)

### 4-1. GEPSクローラの全省庁対応

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 47 | GEPS全省庁URLリストの作成 | GEPSの「全省庁を対象とした入札公告」ページのURLリストを作成 | `data/geps_ministry_urls.csv` |
| 48 | GEPSCrawlerの全省庁対応改造 | `geps_crawler.py` を拡張し、引数で指定した省庁のみを巡回できるように改造 | `geps_crawler.py` |
| 49 | 全省庁一括巡回スクリプトの作成 | `scripts/crawl_all_ministries.py` で全省庁を一巡するスクリプトを作成 | `scripts/crawl_all_ministries.py` |
| 50 | 調達種別フィルタの追加 | 「工事」「委託」「物品」等の調達種別でフィルタリングする機能を追加 | `crawler/parsers/agency_config_loader.py` |

### 4-2. 省政府庁データ正規化

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 51 | 入札案件データモデルの拡張 | 省政府庁の案件に必要なフィールド（府省名、調達主管課等）を追加 | `database/models/bid.py` |
| 52 | 全省庁統一データ抽出ロジック | 各省庁のHTMLから統一フォーマットでデータを抽出する `MinistryBidParser` を作成 | `crawler/parsers/ministry_bid_parser.py` |
| 53 | カテゴリ「国」でのBid登録 | 省政府庁から取得したBidの `agency_id` をカテゴリ「国」のAgencyに設定 | `crawler/pipeline.py` |
| 54 | 省政府庁巡回結果レポート | `scripts/report_ministry_crawl.py` で全省庁の巡回結果を集計 | `scripts/report_ministry_crawl.py` |

---

## Phase 5 — 都道府県別特化クローラテンプレートの開発 (ステップ 55–62)

### 5-1. 都道府県パターンライブラリの構築

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 55 | 都道府県別パターンDirの作成 | `crawler/patterns/prefectures/` に各都道府県用のディレクトリを作成 | `crawler/patterns/prefectures/` |
| 56 | 、愛媛県パターンの一般化 | 既存の `ehime.json` をベースとして、共通パターンと個別パターンに分離 | `crawler/parsers/agency_config/ehime.json` |
| 57 |  北海道パターンの追加 | `crawler/patterns/prefectures/hokkaido.json` を作成 | `crawler/patterns/prefectures/hokkaido.json` |
| 58 | 複数都道府県コンフィグの批量生成 | `scripts/generate_prefecture_configs.py` で47都道府県分のコンフィグを生成 | `scripts/generate_prefecture_configs.py` |

### 5-2. 自動テンプレート生成機能

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 59 | LLM活用構造分析功能 | `crawler/parsers/llm_structure_analyzer.py` にLLMを使って未知のサイト構造を分析させる機能を追加 | `crawler/parsers/llm_structure_analyzer.py` |
| 60 | 自動生成コンフィグの保存 | LLMが生成したコンフィグを `crawler/parsers/agency_config/generated/` に保存 | `crawler/parsers/agency_config/generated/` |
| 61 | 自動生成コンフィグの検証 | 生成されたコンフィグを `scripts/validate_generated_config.py` でテスト | `scripts/validate_generated_config.py` |
| 62 | コンフィグ自動更新机制 | 巡回失敗時にLLMでコンフィグを自動更新する機能を追加 | `crawler/parsers/config_auto_updater.py` |

---

## Phase 6 — 市区町村対応クローラの優先度付けシステム (ステップ 63–68)

### 6-1. 優先度分類机制

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 63 | 人口データCSVの準備 | 総務省発表の市区町村人口データを集めたCSVを準備 | `data/municipality_population.csv` |
| 64 | 優先度自動分類スクリプトの作成 | 人口に応じて高（10万+）、中（5-10万）、低（-5万）を自動分類するスクリプトを作成 | `scripts/classify_priority.py` |
| 65 | Agencyテーブルへの優先度設定 | 分類した優先度を `Agency.priority_level` フィールドに保存 | `database/models/agency.py` |
| 66 | 優先度ベース巡回フィルタの実装 | `GenericCrawler` に `min_priority` パラメータを追加し、巡回対象を制限 | `crawler/generic_crawler.py` |

### 6-2. 巡回頻度の自動調整

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 67 | 巡回間隔設定テーブルの作成 | `crawler_schedule` テーブルにカテゴリ・優先度別の巡回間隔を設定 | `database/models/crawler_schedule.py` |
| 68 | 頻度調整スクリプトの作成 | `scripts/adjust_crawl_frequency.py` で新着頻度に応じて巡回間隔を動的調整 | `scripts/adjust_crawl_frequency.py` |

---

## Phase 7 — 外郭団体（公社・公団・公立病院）クロールの強化 (ステップ 69–72)

### 7-1. 外郭団体マスタの整備

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 69 | 外郭団体マスタCSVの作成 | 主要外郭団体（日本高速道路株式会社、港湾空港技術研究所等）のリストを作成 | `data/quasi_public_agencies.csv` |
| 70 | 外郭団体カテゴリ追加 | 「外郭団体」カテゴリをAgencyCategoryテーブルに追加 | `scripts/init_categories.py` |
| 71 | 外郭団体DB投入スクリプトの作成 | `scripts/import_quasi_public_agencies.py` でCSVからAgencyを一括投入 | `scripts/import_quasi_public_agencies.py` |

### 7-2. 外郭団体対応クローラ機能

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 72 | 認証・ログイン対応功能的追加 | Basic認証、フォーム認証等に対応する `AuthHandler` を追加 | `crawler/auth/auth_handler.py` |

---

## 前提条件チェック（各Phase開始前に実施）

```
[ ] Python 3.14 が `python --version` で確認可能
[ ] `pip install -r requirements.txt` がエラーなく完了
[ ] Playwright browsers が `playwright install` でインストール済み
[ ] Redis が `docker ps` で確認可能
[ ] 既存テストが `pytest tests/ -v` で成功
[ ] `.env` ファイルが存在し、 GEMINI_API_KEY 等が設定済み
```

---

## Phase 別の優先度と工数目安

| Phase | 内容 | 優先度 | 工数目安 |
|-------|------|--------|----------|
| Phase 0 | 現状分析・設計 | 高 | 1週間 |
| Phase 1 | 発注機関カテゴリ分類DB | 高 | 2週間 |
| Phase 2 | 共通クローラ基盤拡張 | 高 | 3週間 |
| Phase 3 | URLレジストリ作成 | 中 | 2週間 |
| Phase 4 | 省政府庁クローラ拡張 | 中 | 2週間 |
| Phase 5 | 都道府県別テンプレート | 中 | 3週間 |
| Phase 6 | 市区町村優先度付け | 低 | 2週間 |
| Phase 7 | 外郭団体対応 | 低 | 1週間 |

---

## 成功基準

- [ ] 全省庁（国）の入札情報を日次で取得可能
- [ ] 47都道府県すべての入札情報を取得可能
- [ ] 人口10万人以上の市区町村の入札情報を取得可能
- [ ] 発注機関をカテゴリ（国/都道府県/市区町村/外郭団体）でフィルタリング可能
- [ ] カテゴリ別のBid件数をダッシュボードで確認可能
- [ ] 新規自治体の追加が設定追加のみで対応可能