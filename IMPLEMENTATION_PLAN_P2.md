# 実装計画書 P2: コード生成・シーダー・モック改善 (36ステップ)

## 概要
gen_crawler.py 生成雛形の完成度向上、prefecture_seeder の実データ投入、テストモックの実用化を実施する。

---

## Phase 1: gen_crawler.py 生成雛形の実装補完 (ステップ 1-12)

### Step 1: TEMPLATE_FETCHER の parse_list 実装例を追加
- BeautifulSoup で `list_selector` 使用し、href 収集 → 絶対 URL 化して返却
- `base_url` と `urljoin` 使用

### Step 2: parse_detail 実装例を追加
- `detail_selector` で詳細要素取得
- `detail_fields` 設定があれば Phase 1 と同様の抽出ロジックをインライン展開
- なければ全テキスト返却 (フォールバック)

### Step 3: save 実装例を追加
- `BidRepository` インポートし、`upsert_bid` 呼び出し例を記述
- セッション管理 (`with get_session() as session:`) を含める

### Step 4: インポート文を動的生成
- `BidRepository` / `get_session` / `normalize_*` 等をテンプレート上部に自動追加

### Step 5: 設定ファイル (YAML) に detail_fields ひな形を追加
- `TEMPLATE_CONFIG` に `detail_fields:` キーとサンプル 3 フィールドを埋め込み

### Step 6: 生成時のバリデーション追加
- `--url` が有効な URL 形式か `validators.url()` でチェック
- `--name` が空でないかチェック

### Step 7: 出力先ディレクトリの自動作成確認
- `config/` と `crawler/agency_lists/` が存在しない場合 `mkdir -p`

### Step 8: 既存ファイル上書き確認プロンプト
- 同名ファイル存在時、`-f/--force` オプションなしでは確認

### Step 9: 生成後の次のアクション表示
- "設定ファイルを編集して detail_fields を調整してください"
- "クローラ登録: python -m crawler.registry.municipality_registry --register ..."

### Step 10: 単体テスト作成 (test_gen_crawler.py)
- 一時ディレクトリで生成 → 構文チェック (`py_compile`) → import 可能か検証

### Step 11: テンプレートを外部ファイル化 (保守性向上)
- `scripts/templates/fetcher_template.py.j2` (Jinja2) に移行
- `scripts/templates/config_template.yaml.j2` 同様

### Step 12: README に gen_crawler 使い方追加

---

## Phase 2: prefecture_seeder 実データ投入 (ステップ 13-24)

### Step 13: 都道府県マスタデータソース確保
- `data/prefectures.csv` (code, name, name_en, region, capital) をリポジトリに追加
- 総務省標準コード (JIS X 0401) 準拠

### Step 14: CSV ローダー関数作成
- `database/seeders/prefecture_seeder.py` に `_load_prefectures_csv()` 追加
- `csv.DictReader` で読み込み、list[dict] 返却

### Step 15: Prefecture モデル確認
- `database/models/prefecture.py` のカラム定義と CSV カラム対応付け

### Step 16: upsert ロジック実装
- `code` を PK とし、`session.merge(prefecture)` で冪等投入

### Step 17: シード実行関数 `seed_prefectures()` 作成
- トランザクション内で全件処理、コミット

### Step 18: CLI エントリーポイント追加
- `if __name__ == "__main__": seed_prefectures()` で直接実行可能に

### Step 19: 既存の placeholder コメント削除
- "The original constants are not available..." 行を削除

### Step 20: 単体テスト作成 (test_prefecture_seeder.py)
- インメモリ SQLite で投入 → 47 件登録確認

### Step 21: 重複実行テスト (2 回目実行で件数不変確認)

### Step 22: マイグレーション連携確認
- `alembic upgrade head` 後すぐに `python -m database.seeders.prefecture_seeder` 実行可能か

### Step 23: 地域別集計クエリ追加 (動作確認用)
- `SELECT region, COUNT(*) FROM prefectures GROUP BY region`

### Step 24: ドキュメント更新 (README セットアップ手順にシーダー実行追加)

---

## Phase 3: テストモック `new_task` 実用化 (ステップ 25-36)

### Step 25: 実際のタスクモデル (Task/Job) 確認
- `database/models/task.py` または `queue/task.py` のフィールド確認

### Step 26: new_task 関数を実モデル準拠に拡張
- 必須フィールド: `id`, `type`, `payload`, `status`, `created_at`, `updated_at`, `retry_count`, `max_retries`

### Step 27: デフォルト値を実運用に近い値に
- `status="pending"`, `retry_count=0`, `max_retries=3`, `created_at=utcnow()`

### Step 28: ヘルパー関数追加
- `create_crawl_task(url, config)`, `create_analysis_task(bid_id)`, `create_notification_task(channel, message)` 等

### Step 29: モックではなくファクトリ関数としてリネーム
- `tests/factories/task_factory.py` に移動、モジュール分離

### Step 30: 既存テストでの import 修正
- `from tests.mocks.new_task import new_task` → `from tests.factories.task_factory import create_task`

### Step 31: 型ヒント完全化
- `TypedDict` で `TaskDict` 定義し、戻り値に付与

### Step 32: pytest fixture 化
- `conftest.py` に `@pytest.fixture def sample_task(): return create_crawl_task(...)` 追加

### Step 33: 非同期タスク対応 (Celery/RQ 風)
- `task_id` を UUID 生成、`queue_name` フィールド追加

### Step 34: シリアライズ/デシリアライズヘルパー
- `to_json()`, `from_json(json_str)` メソッド追加

### Step 35: 単体テスト作成 (test_task_factory.py)
- 全ファクトリ関数の戻り値構造検証

### Step 36: 統合テスト (実際のキューイングフローで投入→ワーカー消費確認)