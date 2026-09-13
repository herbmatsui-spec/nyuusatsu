# 実装計画書 P1: 基盤/インフラ機能の完成 (36ステップ)

## 概要
ConfigDrivenCrawler の詳細抽出・保存、フィールド正規化の全角半角変換、イベントハンドラの DLQ 連携を実装する。

---

## Phase 1: ConfigDrivenCrawler.parse_detail 構造化抽出 (ステップ 1-12)

### Step 1: 設定スキーマに `detail_fields` を追加
- `crawler/config_driven_crawler.py` の `_load_config` 以降で、YAML に `detail_fields` キーを許可する
- 形式: `{ field_name: { selector: "css", attr: "text|href|src", transform: "normalize_amount|normalize_date|..." } }`

### Step 2: parse_detail に detail_fields ループを実装
- BeautifulSoup で `html` をパース
- 各フィールドについて `selector` で要素取得 → `attr` で値取得 → `transform` 関数適用
- 結果を dict で返却

### Step 3: 変換関数マップを定義
- `crawler/parsers/field_normalizer.py` の関数をインポートし、`TRANSFORM_MAP = {"normalize_amount": normalize_amount, ...}` を作成

### Step 4: 不足時のデフォルト値処理
- セレクタがマッチしない場合は `None` または空文字を設定
- 必須フィールドは `required: true` でバリデーション

### Step 5: ネストしたセレクタ対応 (親要素内検索)
- `parent_selector` 指定があれば、まず親要素を取得し、その中で `selector` を実行

### Step 6: 複数要素の取得 (list モード)
- `multiple: true` 指定時は `select` で全要素取得し、リストで返却

### Step 7: 既存の raw text 返却をフォールバックに
- `detail_fields` が未指定の場合は従来通り `soup.get_text()` を返す

### Step 8: 単体テスト作成 (test_config_driven_crawler.py)
- フィクスチャ HTML で各変換パターンを検証
- `tests/unit/test_config_driven_crawler.py` に追加

### Step 9: 設定ファイル例の追加
- `config/sample_detail_fields.yaml` に実例を記載

### Step 10: 型ヒント追加
- `parse_detail` の戻り値を `dict[str, Any]` に変更

### Step 11: ドキュメント更新
- `README.md` の ConfigDrivenCrawler 解説に `detail_fields` 記述追加

### Step 12: 統合テスト (main.py 経由で実行確認)
- 実際の自治体サイト向け設定で動作確認

---

## Phase 2: ConfigDrivenCrawler.save リポジトリ連携 (ステップ 13-24)

### Step 13: リポジトリインポートパス確認
- `database/repositories/bid_repository.py` と `award_result_repository.py` の存在確認

### Step 14: save メソッドシグネチャ拡張
- `save(self, items: List[dict], repository: BidRepository | AwardResultRepository)` に変更

### Step 15: 呼び出し側 (crawl_range 等) でリポジトリ注入
- `main.py` や `scheduler.py` でインスタンス生成時に渡す

### Step 16: BidRepository.save_bid 実装確認
- 既存メソッドがなければ `BidRepository.create` または `upsert` を使用

### Step 17: データマッピング関数作成
- `_map_to_bid_model(item: dict) -> Bid` でフィールド対応付け

### Step 18: 重複チェック (bid_number + agency で UPSERT)
- `repository.upsert_bid(bid)` 呼び出し

### Step 19: AwardResult 連携
- 落札情報が含まれる場合は `AwardResultRepository` も呼ぶ

### Step 20: トランザクション管理
- `database/session.py` の `get_session` コンテキストで wrap

### Step 21: エラーハンドリング・ログ出力
- 失敗時は `logger.error` して継続、成功件数を返却

### Step 22: 既存の print("[SAVE]") を削除

### Step 23: 単体テスト作成 (mock repository)
- `tests/unit/test_config_driven_crawler_save.py`

### Step 24: 統合テスト (DB 実書き込み確認)

---

## Phase 3: field_normalizer.normalize_fullwidth_to_halfwidth 実装 (ステップ 25-30)

### Step 25: mojimoji ライブラリ追加
- `requirements.txt` に `mojimoji>=0.0.12` 追加

### Step 26: 実装置換
```python
import mojimoji
def normalize_fullwidth_to_halfwidth(text: str) -> str:
    return mojimoji.zen_to_han(text, digit=True, ascii=True)
```

### Step 27: 単体テスト追加
- 全角数字・英字・記号・混在ケースを網羅

### Step 28: 既存呼び出し箇所の確認
- `grep -r normalize_fullwidth_to_halfwidth` で使用箇所特定し動作確認

### Step 29: パフォーマンス確認 (大量文字列で遅延ないか)

### Step 30: ドキュメント更新 (README の正規化機能欄)

---

## Phase 4: イベントハンドラ DLQ 連携 (ステップ 31-36)

### Step 31: DLQ 用 Redis キー設計
- `dlq:events:{handler_name}` 形式のリスト構造

### Step 32: queue/redis_client.py に push_dlq 関数追加
```python
def push_dlq(handler_name: str, event_data: dict, error: str):
    key = f"dlq:events:{handler_name}"
    payload = json.dumps({"event": event_data, "error": error, "timestamp": utcnow()})
    redis_client.rpush(key, payload)
```

### Step 33: base_handler._handle_failure で push_dlq 呼び出し
- `from queue.redis_client import push_dlq` インポート

### Step 34: DLQ 再処理スクリプト作成
- `scripts/reprocess_dlq.py` : キー指定で全件再実行 or 個別再実行

### Step 35: 監視用メトリクス追加
- `services/quality_metrics_service.py` に DLQ 滞留数カウント追加

### Step 36: 統合テスト (意図的エラー発生 → DLQ 積み上がり → 再処理成功確認)