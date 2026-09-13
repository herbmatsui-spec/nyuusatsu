# 都道府県マスタデータの seeding 手順

## 概要
このドキュメントは、`prefectures` テーブルおよび関連する `agencies` テーブルへの都道府県マスタデータの初期投入手順について説明します。

## 前提条件
- Python 3.12 以上がインストールされていること
- 必要な Python パッケージがインストールされていること（`pip install -r requirements.txt`）
- データベースが初期化されていること（`bids_system.db` が存在すること）

## 手順

### 1. 都道府県 CSV データの準備
都道府県マスタデータは、`data/prefectures.csv` ファイルから読み込まれます。
このファイルは、総務省の全国地方公共団体コードリストから抽出され、以下のカラムを含みます：
- id: 連番（1-47）
- name: 都道府県名（漢字）
- code: 都道府県コード（2桁、例えば "01" は北海道）
- kana_name: 都道府県名（カナ）
- region_code: 地域コード（1-9 の数字）

ファイルが存在しない場合は、スクリプトが自動的に総務省のリストから生成します。

### 2. seeding スクリプトの実行
以下のコマンドを実行して、都道府県データをデータベースに投入します：

```bash
python scripts/seed_prefectures.py
```

このスクリプトは以下の処理を行います：
1. 必要なテーブルが存在しない場合は作成します（`create_tables()`）
2. `prefectures` テーブルに都道府県マスタデータを投入します（重複はスキップ）
3. 北海道専用の bid_source（web と geps）を投入します
4. 全都道府県の GEPS bid_source を投入します（北海道の GEPS は重複のためスキップ）
5. 投入結果をコンソールに出力します

### 3. 投入結果の確認
スクリプト実行後、以下のクエリでデータが正しく投入されているか確認できます：

```sql
-- prefectures テーブルの件数確認（47 件であるべき）
SELECT COUNT(*) FROM prefectures;

-- agencies テーブルの都道府県レコード件数確認（47 件であるべき）
SELECT COUNT(*) FROM agencies WHERE category_id = 2; -- category_id=2 は「都道府県」カテゴリ

-- サンプルデータの表示
SELECT id, code, name, kana_name, region_code FROM prefectures LIMIT 5;
```

### 4. データの更新について
都道府県マスタデータは頻繁に変更されませんが、変更があった場合は：
1. `data/prefectures.csv` を更新します（必要に応じて総務省のリストから再取得）
2. 再度 `python scripts/seed_prefectures.py` を実行します
   （重複データはスキップされるため、新しいデータのみが追加または更新されます）

## 注意事項
- このスクリプトは `agencies` テーブルへの都道府県レコードの投入は行いません。都道府県レコードは別途プロセス（例：`seed_agency_inventory.py` など）によって投入されています。
- すでにデータが存在する場合は、重複を避けるために新規投入は行われません。
- 実際の運用では、都道府県マスタデータはほぼ変更されないため、頻繁な再投入は必要ありません。