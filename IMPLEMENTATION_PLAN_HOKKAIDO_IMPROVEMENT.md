# 北海道入札クローラー改善 — 詳細実装計画書

> **目標**: Bidモデルにprefecture_code追加、BidStorageService.save_bid()にprefecture_code対応、詳細ページスクレイピング実装の3改善を72ステップで完了させる
> **前提**: Python 3.14, SQLite, Playwright導入済み, 低性能LLM環境でも動作する堅実な実装

---

## Phase 0 — 事前調査・現状確認 (ステップ 1–6)

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 1 | Bidモデルの現在のカラム一覧を確認 | `PRAGMA table_info(bids)` で全カラム名・タイプ・NULL許可を確認 | — |
| 2 | BidStorageService.save_bid()の引数を確認 | [bid_storage_service.py:9](services/bid_storage_service.py:9) で現在の署名・処理内容を把握 | `services/bid_storage_service.py` |
| 3 | crawl_scheduler.pyの_crawl_geps()と_crawl_web()を確認 | [crawl_scheduler.py:129](services/crawl_scheduler.py:129) と [crawl_scheduler.py:188](services/crawl_scheduler.py:188) でbid_data作成部分を確認 | `services/crawl_scheduler.py` |
| 4 | BidSourceモデルのprefecture_idを確認 | `BidSource` に `prefecture_id` があり、Prefectureとリレーションがあるか確認 | `database/models/bid_source.py` |
| 5 | Prefectureモデルのcode形式を確認 | `JP-01` のようなコード体系がどのテーブルで管理されているか確認 | `database/models/prefecture.py` |
| 6 | 既存のmigrationファイル命名規則を確認 | `alembic/versions/` 下のファイル名パターン（連番? 日付?）を確認 | `alembic/versions/` |

---

## Phase 1 — Bidモデルにprefecture_code追加 (ステップ 7–18)

### 1-1. Bidモデル編集

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 7 | Bidモデルにprefecture_codeカラム追加 | [bid.py:10](database/models/bid.py:10) の `id` の後らに `prefecture_code: Mapped[Optional[str]] = mapped_column(String(20))` を追加 | `database/models/bid.py` |
| 8 | prefecture_codeにインデックス追加 | `mapped_column(String(20), index=True)` でインデックス付きに | `database/models/bid.py` |
| 9 | Bidモデルのimport文確認 | `String` が既にimportされているか確認、なければ追加 | `database/models/bid.py` |

### 1-2. Alembicマイグレーション作成

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 10 | alembic revision --autogenerate でmigration生成 | `alembic revision --autogenerate -m "add prefecture_code to bids"` を実行 | `alembic/versions/` |
| 11 | 生成されたmigrationファイルの内容確認 | `alembic/versions/` 下に作成されたファイルを開く | `alembic/versions/xxxx_add_prefecture_code.py` |
| 12 | migrationのupgrade()にNULL許容確認 | `prefecture_code` が NULL 許容であることを確認（既存データ対応） | `alembic/versions/xxxx_add_prefecture_code.py` |
| 13 | migrationのdowngrade()確認 | `drop_column('prefecture_code')` が含まれていることを確認 | `alembic/versions/xxxx_add_prefecture_code.py` |
| 14 | `alembic upgrade head` でマイグレーション実行 | DBに `prefecture_code` カラムが追加されることを確認 | — |
| 15 | `PRAGMA table_info(bids)` でカラム追加確認 | 新しいカラムがテーブルに存在することを確認 | — |
| 16 | `alembic downgrade -1` でロールバック確認 | カラムが削除されることを確認後、`alembic upgrade head` で再適用 | — |

---

## Phase 2 — BidStorageService.save_bid()にprefecture_code対応 (ステップ 19–30)

### 2-1. BidStorageService編集

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 17 | save_bid()の引数にprefecture_code追加 | [bid_storage_service.py:9](services/bid_storage_service.py:9) の `def save_bid(self, bid_data: dict)` を `def save_bid(self, bid_data: dict, prefecture_code: Optional[str] = None)` に変更 | `services/bid_storage_service.py` |
| 18 | save_bid()内のBid作成時にprefecture_codeを設定 | [bid_storage_service.py:34](services/bid_storage_service.py:34) の `Bid()` 作成部分で `prefecture_code=prefecture_code` を追加 | `services/bid_storage_service.py` |
| 19 | save_bid()内のupdate処理にprefecture_code追加 | [bid_storage_service.py:18](services/bid_storage_service.py:18) の `update_data` 辞書に `prefecture_code` を追加 | `services/bid_storage_service.py` |
| 20 | _extract_budget_amount()の後ろに空行追加 | コード整形（可読性維持） | `services/bid_storage_service.py` |

### 2-2. crawl_scheduler.py編集

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 21 | _crawl_geps()でPrefectureコード取得 | [crawl_scheduler.py:129](services/crawl_scheduler.py:129) 付近で `source.prefecture_id` からPrefecture.codeを取得する処理を追加 | `services/crawl_scheduler.py` |
| 22 | _crawl_geps()のsave_bid()呼び出し修正 | [crawl_scheduler.py:170](services/crawl_scheduler.py:170) の `self.storage.save_bid(bid_data)` に第2引数としてprefecture_codeを追加 | `services/crawl_scheduler.py` |
| 23 | _crawl_web()でPrefectureコード取得 | [crawl_scheduler.py:188](services/crawl_scheduler.py:188) 付近で source.prefecture_id からPrefecture.codeを取得 | `services/crawl_scheduler.py` |
| 24 | _crawl_web()のsave_bid()呼び出し修正 | [crawl_scheduler.py:220](services/crawl_scheduler.py:220) の `self.storage.save_bid(bid_data)` に第2引数としてprefecture_codeを追加 | `services/crawl_scheduler.py` |
| 25 | Prefecture取得用ヘルパーメソッド追加 | `_get_prefecture_code(prefecture_id: int) -> Optional[str]` を CrawlScheduler 内に追加 | `services/crawl_scheduler.py` |
| 26 | Prefectureモデルimport確認 | [crawl_scheduler.py:8](services/crawl_scheduler.py:8) に `from database.models import Prefecture` が含まれているか確認 | `services/crawl_scheduler.py` |

### 2-3. 動作確認

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 27 | importテスト実行 | `python -c "from services.bid_storage_service import BidStorageService; print('OK')"` が成功することを確認 | — |
| 28 | importテスト実行 | `python -c "from services.crawl_scheduler import CrawlScheduler; print('OK')"` が成功することを確認 | — |
| 29 | save_bid()の引数確認 | `python -c "from services.bid_storage_service import BidStorageService; import inspect; print(inspect.signature(BidStorageService.save_bid))"` で署名確認 | — |
| 30 | 北海道でテスト実行 | `python scripts/crawl_hokkaido.py` を実行してprefecture_code='JP-01'でBidが保存されることを確認 | `scripts/crawl_hokkaido.py` |

---

## Phase 3 — 詳細ページスクレイピング実装 (ステップ 31–54)

### 3-1. 既存コード調査

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 31 | crawler_scheduler.py:216のTODOコメント確認 | `pass # TODO: 詳細ページスクレイピングを実装` を見つける | `services/crawl_scheduler.py` |
| 32 | GenericCrawlerのcrawl_site()戻り値確認 | [generic_crawler.py:81](crawler/generic_crawler.py:81) で返される `CrawlResult` の構造を確認 | `crawler/generic_crawler.py` |
| 33 | CrawlResultモデルの定義確認 | [crawler/models/crawl_result.py](crawler/models/crawl_result.py) で利用可能なフィールドを確認 | `crawler/models/crawl_result.py` |
| 34 | PDFDownloader.download()の戻り値確認 | [downloader.py](crawler/downloader.py) で `(success, file_path, sha256, error_msg)` 形式を確認 | `crawler/downloader.py` |
| 35 | 詳細ページ（PDF）から取得すべきフィールド一覧 | budget, deadline, qualifications, deliverables, announcement_date を抽出対象として定義 | — |

### 3-2. 詳細ページ取得クラス作成

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 36 | BidDetailExtractorクラスの骨子作成 | `crawler/detail_extractor.py` に `class BidDetailExtractor` を作成 | `crawler/detail_extractor.py` |
| 37 | fetch_detail_page()メソッド実装 | URLからHTMLまたはPDFを取得する基本メソッド | `crawler/detail_extractor.py` |
| 38 | extract_from_html()メソッド実装 | BeautifulSoupでHTMLから入札情報を抽出 | `crawler/detail_extractor.py` |
| 39 | extract_from_pdf()メソッド実装 | PDFからテキスト抽出（PyPDF2またはpdfplumber） | `crawler/detail_extractor.py` |
| 40 | extract_budget()メソッド実装 | 予算額を正規表現で抽出（例: 「金額」, 「予算額」, 円/円/万円） | `crawler/detail_extractor.py` |
| 41 | extract_deadline()メソッド実装 | 締切日を正規表現で抽出（例: 「締切」, 「期限」, 年/月/日） | `crawler/detail_extractor.py` |
| 42 | extract_qualifications()メソッド実装 | 参加資格を抽出（例: 「資格」, 「条件」, 「要件」） | `crawler/detail_extractor.py` |
| 43 | extract_deliverables()メソッド実装 | 成果物を抽出（例: 「成果物」, 「納入物」） | `crawler/detail_extractor.py` |
| 44 | extract_announcement_date()メソッド実装 | 公告日を抽出（例: 「公告」, 「公表」） | `crawler/detail_extractor.py` |

### 3-3. CrawlSchedulerへの統合

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 45 | BidDetailExtractorのimport追加 | [crawl_scheduler.py](services/crawl_scheduler.py) に `from crawler.detail_extractor import BidDetailExtractor` を追加 | `services/crawl_scheduler.py` |
| 46 | _crawl_web()内に詳細ページ取得処理追加 | [crawl_scheduler.py:216](services/crawl_scheduler.py:216) の `pass # TODO` を `detail_extractor = BidDetailExtractor()` 作成に置き換え | `services/crawl_scheduler.py` |
| 47 | 詳細ページからのデータ抽出処理追加 | `detail_data = detail_extractor.extract(item.get('url'))` を呼び出して結果を取得 | `services/crawl_scheduler.py` |
| 48 | 抽出した数据进行bid_dataへのマージ | `bid_data.update(detail_data)` で基本データと詳細データを統合 | `services/crawl_scheduler.py` |
| 49 | 例外処理の追加 | 詳細ページ取得失敗時にログ出力して処理を続行（フォールバック） | `services/crawl_scheduler.py` |
| 50 | _crawl_geps()にも詳細ページ取得追加 | GEPSでも詳細ページから情報を取得するように同じ処理を追加 | `services/crawl_scheduler.py` |

### 3-4. 正規表現パターンの整備

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 51 | 日付パターン整理 | `r'\d{4}[/\-年]\d{1,2}[/\-月]\d{1,2}[/\-日]?'` のような日付正規表現を定数として定義 | `crawler/detail_extractor.py` |
| 52 | 金額パターン整理 | `r'[\d,]+万?円'` や `r'¥?[\d,]+'` のような金額正規表現を定数として定義 | `crawler/detail_extractor.py` |
| 53 | キーワードマッピング作成 | 「予算額」「締切」「参加資格」などの日本語キーワードからフィールド名へのマッピング | `crawler/detail_extractor.py` |
| 54 | テスト用HTMLサンプル作成 | 詳細ページのHTML断片をテストデータとして `tests/fixtures/detail_page_sample.html` に保存 | `tests/fixtures/detail_page_sample.html` |

---

## Phase 4 — テスト・品質保証 (ステップ 55–66)

### 4-1. ユニットテスト

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 55 | BidStorageService.save_bid()のユニットテスト作成 | prefecture_codeありなしで保存テスト | `tests/test_bid_storage_service.py` |
| 56 | BidDetailExtractor.extract_budget()のテスト | 金額文字列からの抽出テスト（例: "1,000万円" → 10000000） | `tests/test_detail_extractor.py` |
| 57 | BidDetailExtractor.extract_deadline()のテスト | 日付文字列からの抽出テスト | `tests/test_detail_extractor.py` |
| 58 | BidDetailExtractor.extract_qualifications()のテスト | 参加資格テキストの抽出テスト | `tests/test_detail_extractor.py` |
| 59 | BidDetailExtractor.extract_from_html()のテスト | サンプルHTMLからの抽出テスト | `tests/test_detail_extractor.py` |

### 4-2. 結合テスト

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 60 | 北海道での結合テスト | `python scripts/crawl_hokkaido.py` を実行してBidが正しく保存されることを確認 | `scripts/crawl_hokkaido.py` |
| 61 | prefecture_code確認テスト | `SELECT prefecture_code FROM bids WHERE prefecture_code = 'JP-01'` でデータ存在確認 | — |
| 62 | 詳細情報抽出テスト | 保存されたBidのbudget, deadline, qualificationsに値が入っているか確認 | — |
| 63 | 重複BidのUPSERTテスト | 同一URLで2回クロールしてデータが更新されることを確認 | — |

### 4-3. E2Eテスト

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 64 | 北海道1件でのE2Eテスト | `python scripts/collect_all_sync.py --prefecture-id 1 --limit 1` を実行 | `scripts/collect_all_sync.py` |
| 65 | 取得データの完全性確認 | filename, source_url, prefecture_code, budget, deadline, organization_name がすべて取得できているか確認 | — |
| 66 | 全コンポーネントimportテスト | `python -c "from crawler.detail_extractor import *; from services.bid_storage_service import *; from services.crawl_scheduler import *; print('OK')"` が成功することを確認 | — |

---

## Phase 5 — リファクタリング・コード整理 (ステップ 67–72)

### 5-1. 不要コード削除

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 67 | TODOコメント削除 | [crawl_scheduler.py:216](services/crawl_scheduler.py:216) の `pass # TODO` を削除済み確認 | `services/crawl_scheduler.py` |
| 68 | 空のcommit()/close()削除検討 | [bid_storage_service.py:62](services/bid_storage_service.py:62) の空実装を削除またはコメント追加 | `services/bid_storage_service.py` |

### 5-2. ドキュメント更新

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 69 | BidStorageService.save_bid()のdocstring更新 | 引数・戻り値のドキュメントを更新 | `services/bid_storage_service.py` |
| 70 | BidDetailExtractorのdocstring作成 | 各メソッドのdocstringを作成 | `crawler/detail_extractor.py` |
| 71 | README.md更新 | 変更点を追加（prefecture_code対応、詳細ページスクレイピング対応） | `README.md` |

### 5-3. 最終確認

| # | タスク | 説明・変更点 | ファイル |
|---|--------|-------------|----------|
| 72 | 全テスト実行・合格確認 | `python -m pytest tests/test_bid_storage_service.py tests/test_detail_extractor.py -v` を実行し全テスト合格を確認 | `tests/` |

---

## 前提条件チェック（各Phase開始前に実施）

```
[ ] Python 3.14 が `python --version` で確認可能
[ ] `pip install -r requirements.txt` がエラーなく完了
[ ] `python -m playwright install chromium` が成功
[ ] `.env` に GEMINI_API_KEY=... が設定済み
[ ] `python -c "from database.engine import engine; print(engine.url)"` でDB接続確認
[ ] `alembic current` で現在のマイグレーションバージョン確認
[ ] `python -c "from database.models import Bid; print('OK')"` が成功
[ ] `python -c "from services.bid_storage_service import BidStorageService; print('OK')"` が成功
```

## 緊急時の対応コマンド

```bash
# マイグレーションロールバック
alembic downgrade -1

# マイグレーション再適用
alembic upgrade head

# Bidテーブル確認
python -c "import sqlite3; conn = sqlite3.connect('bids_system.db'); cur = conn.cursor(); cur.execute('PRAGMA table_info(bids)'); print([r[1] for r in cur.fetchall()]); conn.close()"

# prefecture_code確認
python -c "import sqlite3; conn = sqlite3.connect('bids_system.db'); cur = conn.cursor(); cur.execute('SELECT prefecture_code, COUNT(*) FROM bids GROUP BY prefecture_code'); print(cur.fetchall()); conn.close()"

# 全テスト実行
python -m pytest tests/test_bid_storage_service.py tests/test_detail_extractor.py -v

# 北海道クロールテスト
python scripts/crawl_hokkaido.py
```

## ファイル変更一覧

| ファイル | 変更内容 |
|---------|----------|
| `database/models/bid.py` | prefecture_codeカラム追加 |
| `alembic/versions/xxxx_add_prefecture_code.py` | 新規作成（マイグレーション） |
| `services/bid_storage_service.py` | save_bid()にprefecture_code引数追加 |
| `services/crawl_scheduler.py` | prefecture_code取得・渡渡し追加、詳細ページスクレイピング実装 |
| `crawler/detail_extractor.py` | 新規作成（詳細ページスクレイピング） |
| `tests/test_bid_storage_service.py` | 新規作成（ユニットテスト） |
| `tests/test_detail_extractor.py` | 新規作成（ユニットテスト） |
| `tests/fixtures/detail_page_sample.html` | 新規作成（テストデータ） |
| `README.md` | 変更点追記 |