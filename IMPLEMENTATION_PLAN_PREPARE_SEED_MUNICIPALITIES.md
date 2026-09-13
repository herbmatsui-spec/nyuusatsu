# 全国市区町村マスタデータを準備しデータベースに投入する
## ステップ 1-24

1. `scripts/fetch_municipality_codes.py` ファイルが存在することを確認する（総務省APIまたは公開CSVから市町村コード取得）
2. スクリプト内容を読み、どのようにデータを取得・整形するか理解する
3. 必要に応じて、Python依存ライブラリ（requests, pandas等）がインストールされているか確認する
4. スクリプトを実行し、`data/municipality_codes_raw.csv` または同様の生ファイルを取得する
5. 取得した生データを確認し、不要なカラムやヘッダーがある場合は整理する
6. `scripts/prepare_municipality_codes.py` ファイルが存在することを確認する（生データを整形し、都道府県コード・市区町村コード・名前等に分割）
7. スクリプト内容を読み、整形ロジックを理解する
8. 整形スクリプトを実行し、`data/municipalities.csv` （または `data/municipality_prepared.csv`）を生成する
9. 生成されたCSVのフォーマットを確認（例: id, name, prefecture_code, municipality_code, kana_name, region_code）
10. 必要に応じて、データベースの `agencies` テーブルに市区町村レコードを投入するスクリプトがあるか確認する（例: `scripts/import_agencies.py`）
11. スクリプトが存在しない場合は、雛形を作成するか、`import_ministries.py` を参考に新規作成する
12. データベース接続情報を確認する（`.env`等）
13. `alembic`マイグレーションで `agencies` テーブルが存在し、`municipality_code` カラムがあるか確認する
14. `agency_categories` テーブルに「市区町村」カテゴリが登録されているか確認し、無ければ先に投入する
15. `scripts/import_agencies.py` （または市区町村専用スクリプト）を実行し、`municipalities.csv` からデータを読み込み、`agencies` テーブルへ投入する
16. 投入時は、`category_id` を「市区町村」カテゴリのIDに設定し、`municipality_code` カラムにコードを格納する
17. `priority_level` は後工程で人口ベースで設定するため、一時的に中（0）とするかNULLとする
18. `base_url` と `bid_url_pattern` は後 etapas で設定するため、一旦NULLまたは空文字列とする
19. スクリプト実行中のログを確認し、エラーが発生しないか監視する
20. 投入が完了したら、データベースクエリで件数を確認する (`SELECT COUNT(*) FROM agencies WHERE category_id = (SELECT id FROM agency_categories WHERE name='市区町村');`)
21. 約1700件であることを確認する（正確な件数は自治体数により変動）
22. サンプルデータを表示し、内容が正しいか目視確認する（自治体名とコードが対応しているか）
23. 重複や不正なレコードがないか、ユニーク制約違反がないか確認するクエリを実行する
24. 正常に投入できたら、スクリプトのログ出力を確認し、成功メッセージがあるか確認し、次のステップ（都道府県別設定ファイル生成）に進む準備ができたことを確認する