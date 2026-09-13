# 国政府庁マスタデータをデータベースに投入する
## ステップ 1-24

1. `scripts/import_ministries.py` ファイルが存在することを確認する
2. スクリプト内容を読み、どのようにデータを投入するか理解する
3. 必要な入力データ（例: `data/ministries.csv`）が存在するか確認する
4. CSVが存在しない場合は、各府省の名前リストを手作業でまとめCSVを作成する（フォーマット: id, name, kana_name 等）
5. データベース接続情報を確認する（`.env`等）
6. `alembic`マイグレーションで `agencies` テーブルに `category_id` カラムが存在するか確認する（国カテゴリ用FK）
7. `agency_categories` テーブルに「国」カテゴリが登録されているか確認し、無ければ先に投入する（スクリプトまたは手動）
8. `scripts/import_ministries.py` を実行してデータ投入を開始する
9. スクリプト実行中のログを確認し、エラーが発生しないか監視する
10. 投入が完了したら、データベースクエリで件数を確認する (`SELECT COUNT(*) FROM agencies WHERE category_id = (SELECT id FROM agency_categories WHERE name='国');`)
11. 期待する府省数（約20-30件）であることを確認する
12. サンプルデータを表示し、内容が正しいか目視確認する (`SELECT * FROM agencies WHERE category_id = (SELECT id FROM agency_categories WHERE name='国') LIMIT 5;`)
13. 必要に応じて、`base_url` と `bid_url_pattern` を後 etapas で設定するため、一旦NULLまたは空文字列とする
14. `priority_level` はデフォルトで中（またはスクリプトで指定）とする
15. 投入後の`agencies`テーブル全体件数も確認する
16. 正常に投入できたら、スクリプトのログ出力を確認し、成功メッセージがあるか確認する
17. 失敗した場合は、エラーメッセージに従い修正を行う（CSVパス、DB接続、カテゴリID不整合等）
18. 必要に応じて、府省データの更新スクリプトも同様に作成しておく
19. 完了したら、`docs/` または `README.md` に投入手順を記録する
20. すべての府省が正しく登録されているか、重複がないか確認するクエリを実行する
21. `agency_categories` テーブルの「国」カテゴリの `priority` フィールドがある場合は適切に設定する
22. データ投入後に、簡易的なクロールテストスクリプト（例: 1件だけ取得してみる）を走らせてもよいが、必須ではない
23. 次のステップ（全国市区町村データ準備）に進む準備ができたことを確認する
24. 作業完了のコミットメッセージ例を記録しておく（例: "feat: import national ministries master data"）