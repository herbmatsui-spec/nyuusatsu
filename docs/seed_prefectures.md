# 都道府県マスタデータ投入手順

## 概要
このドキュメントは、都道府県マスタデータ（prefectures テーブルおよび agencies テーブルの都道府県レコード）をデータベースに投入する手順を説明します。

## 前提条件
- Python 3.12 以上
- 必要な Python パッケージがインストール済み（`pip install -r requirements.txt`）
- データベースファイル `bids_system.db` が存在し、テーブルが作成済み（または `create_tables` 関数により自動作成される）
- `data/prefecture_urls.csv` が存在すること（都道府県の市区町村コードを取得するため）

## 手順

### ステップ 1: 都道府県マスタおよび入札ソースの投入
```bash
python scripts/seed_prefectures.py
```
このスクリプトは以下を実行します：
- `prefectures` テーブルに都道府県マスタデータを 47 件投入
- `bid_sources` テーブルに北海道専用ソース（web + geps）および全都道府県の GEPS ソースを投入
- 実行ログを確認し、正常に完了したことを確認

### ステップ 2: 都道府県レコードの agencies テーブルへの投入
```bash
python scripts/import_agencies.py
```
このスクリプトは以下を実行します：
- `data/prefecture_urls.csv` を読み込み、都道府県名と市区町村コードのマッピングを取得
- 既存の都道府県レコード（`category_id=2`）を削除
- 各都道府県に対して `agencies` テーブルへレコードを挿入
  - `name`: 都道府県名
  - `type`: 空文字列（後段階で設定）
  - `region`: 空文字列（後段階で設定）
  - `base_url`: 空文字列（後段階で設定）
  - `municipality_code`: 都道府県の市区町村コード（6桁）
  - `category_id`: 2（都道府県）
  - `priority_level`: 1（中、デフォルト）
  - `system_type`: 空文字列（後段階で設定）
  - `created_at`, `updated_at`: 現在タイムスタンプ
- 投入後のレコード数を確認し、正常に完了したことを確認

### ステップ 3: 検証
以下のクエリを実行し、データが正しく投入されていることを確認してください。

#### 都道府県マスタデータの確認
```sql
SELECT COUNT(*) FROM prefectures; -- 期待値: 47
SELECT id, code, name, kana_name, region_code, priority, official_url FROM prefectures LIMIT 3;
```

#### agencies テーブルの都道府県レコード確認
```sql
SELECT COUNT(*) FROM agencies WHERE category_id=2; -- 期待値: 47
SELECT id, name, municipality_code, priority_level, base_url FROM agencies WHERE category_id=2 LIMIT 3;
```

#### 都道府県コードの整合性確認
```sql
SELECT a.id, a.name, a.municipality_code, p.code as pref_code,
       CASE WHEN SUBSTR(a.municipality_code, 1, 2) = p.code THEN 'OK' ELSE 'MISMATCH' END as match
FROM agencies a
JOIN prefectures p ON a.name = p.name
WHERE a.category_id = 2
LIMIT 5;
```
すべての行で `match` が `OK` であることを確認。

## トラブルシューティング
- エラーが発生した場合は、コンソール出力のエラーメッセージを確認してください。
- 都道府県データが見つからない場合は、まず `scripts/seed_prefectures.py` を実行してマスタデータを投入してください。
- CSV ファイルが読み込めない場合は、`data/prefecture_urls.csv` が存在し、 UTF-8 エンコーディングであることを確認してください。

## 次のステップ
この手順が完了したら、次のステップである「国政府庁データ投入」に進む準備が整っています。
