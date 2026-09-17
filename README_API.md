# 入札システム API (Search API)

FastAPI ベースの検索 API です。入札案件・落札結果・発注予測・品質メトリクス・保存検索・アラート設定 などを提供します。

## エンドポイント一覧

| カテゴリ        | メソッド | パス                        | 説明                         | 認証 |
|---------------|----------|----------------------------|------------------------------|------|
| Bids          | GET      | `/bids`                    | 入札案件検索・一覧          | 不要 |
| Bids          | GET      | `/bids/{bid_id}`           | 入札詳細取得                 | 不要 |
| Awards        | GET      | `/awards`                  | 落札結果検索・一覧          | 不要 |
| Awards        | GET      | `/awards/{award_id}`       | 落札結果詳細取得             | 不要 |
| Forecasts     | GET      | `/api/forecasts`           | 発注予測一覧                | 不要 |
| Forecasts     | GET      | `/api/forecasts/{id}`      | 発注予測詳細取得             | 不要 |
| Price         | GET      | `/price_predictions/{bid_id}` | 価格予測取得              | 不要 |
| Quality       | GET      | `/quality/metrics`         | 品質メトリクス取得          | 不要 |
| Saved Search  | GET      | `/me/saved_searches`       | 保存検索一覧                | 要   |
| Saved Search  | POST     | `/me/saved_searches`       | 保存検索作成                | 要   |
| Saved Search  | GET      | `/me/saved_searches/{id}`  | 保存検索詳細取得             | 要   |
| Saved Search  | PUT      | `/me/saved_searches/{id}`  | 保存検索更新                | 要   |
| Saved Search  | DELETE   | `/me/saved_searches/{id}`  | 保存検索削除                | 要   |
| Alerts        | GET      | `/me/alerts`               | アラート設定一覧            | 要   |
| Alerts        | POST     | `/me/alerts`               | アラート設定作成            | 要   |
| Alerts        | PUT      | `/me/alerts/{id}`          | アラート設定更新            | 要   |
| Metrics       | GET      | `/metrics/summary`         | パイプラインサマリー        | 不要 |
| Metrics       | GET      | `/metrics/health`          | システムヘルス              | 不要 |

**認証が必要なエンドポイント** は `Authorization: Bearer <JWTトークン>` ヘッダーを指定してください。

## ローカル開発

### 前提条件

- Python 3.12+
- PostgreSQL または SQLite (デフォルト)

### 起動方法

```bash
# 1. 依存関係をインストール
pip install -r requirements.txt

# 2. 環境変数を設定（.env ファイルを作成）
cp .env.example .env
# DATABASE_URL、JWT secret 等を設定

# 3. API サーバーを起動
uvicorn search_api.main:app --host 0.0.0.0 --port 8000

# 4. ドキュメントを確認
# http://localhost:8000/docs       (Swagger UI)
# http://localhost:8000/redoc      (ReDoc)
# http://localhost:8000/openapi.json (OpenAPI spec)
```

## Docker での起動

```bash
# search_api サービスのみ起動
docker-compose up search_api

# 全サービス起動（Streamlit, FastAPI, Redis など）
docker-compose up -d
```

search_api は `http://localhost:8001` でアクセスできます。

## フィルタリング

### GET /bids

| パラメータ           | 型    | 必須 | 説明                     |
|---------------------|-------|------|--------------------------|
| `q`                 | str   | いいえ | キーワード検索           |
| `prefecture`         | list  | いいえ | 都道府県コード           |
| `organization`      | str   | いいえ | 発注機関名               |
| `budget_min`        | int   | いいえ | 予算下限（円）           |
| `budget_max`        | int   | いいえ | 予算上限（円）           |
| `published_after`   | date  | いいえ | 公告日（開始）           |
| `published_before`  | date  | いいえ | 公告日（終了）           |
| `page`              | int   | いいえ | ページ番号（デフォルト 1）|
| `size`              | int   | いいえ | ページサイズ（デフォルト 20）|

### GET /awards

| パラメータ           | 型    | 必須 | 説明                     |
|---------------------|-------|------|--------------------------|
| `q`                 | str   | いいえ | キーワード検索           |
| `winner_name`       | str   | いいえ | 落札者名                 |
| `agency_name`       | str   | いいえ | 機関名                   |
| `budget_min`        | int   | いいえ | 予算下限（円）           |
| `budget_max`        | int   | いいえ | 予算上限（円）           |
| `awarded_after`     | date  | いいえ | 落札日（開始）           |
| `awarded_before`    | date  | いいえ | 落札日（終了）           |
| `bid_id`            | int   | いいえ | 関連入札ID               |

## エラーレスポンス形式

すべてのエラーは統一フォーマットで返却されます。

```json
{
  "error": {
    "code": "HTTP_404",
    "message": "Bid not found"
  }
}
```

バリデーションエラーの場合は `details` フィールドも含まれます。

## テスト

```bash
# API テスト
pytest tests/test_search_api.py -v

# カバレッジ付き実行
pytest tests/test_search_api.py -v --cov=search_api --cov-report=term-missing
```
