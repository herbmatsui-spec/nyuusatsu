# URLレジストリと同期システムを実装し、agencyのbase_url/bid_patternを自動更新する
## ステップ 1-24

1. `crawler/registry/` ディレクトリが存在するか確認し、存在しない場合は作成する
2. レジストリ基底クラス `crawler/registry/__init__.py` を作成し、共通インターフェースを定義する（`get_url(agency_code)` 等）
3. 都道府県レジストリ `crawler/registry/prefecture_registry.py` を作成し、`data/prefecture_urls.csv` からURLを読み込むロジックを実装する
4. 市区町村レジストリ `crawler/registry/city_registry.py` を作成し、`data/city_urls.csv` からURLを読み込むロジックを実装する
5. 全市区町村レジストリ `crawler/registry/municipality_registry.py` を作成し、必要に応じてテンプレートベースでURLを生成するロジックを実装する
6. URLバリデーター `crawler/registry/url_validator.py` を作成し、HEADリクエストや軽量GETでURLのアクセス可否を確認する関数を実装する
7. URL変更検知機能 `crawler/registry/url_change_detector.py` を作成し、過去のレスポンスと比較して変化があればフラグを立てるロジックを実装する
8. レジストリからDBへ同期するスクリプト `scripts/sync_registry_to_db.py` を作成するか、既存があるか確認する
9. スクリプト内容を読み、どのようにレジストリを走らせて `agencies` テーブルの `base_url` と `bid_url_pattern` を更新するか理解する
10. 必要な依存ライブラリ（requests等）がインストールされているか確認する
11. スクリプト実行前に、対象とするレジストリ種別（都道府県、市区町村等）と対象条件（例: 未設定のみ）を決定する
12. `python scripts/sync_registry_to_db.py --type prefecture` などで実行を開始する
13. スクリプト実行中のログを確認し、エラーが発生しないか監視する（ネットワークエラー等は一時的にスキップしてもよい）
14. 更新件数をログで確認し、期待する件数と一致するか確認する
15. データベースクエリで更新結果を確認する（例: `SELECT COUNT(*) FROM agencies WHERE base_url IS NOT NULL;`）
16. サンプルレコードを表示し、URLが正しく設定されているか目視確認する
17. URLバリデーションステップを含めている場合は、無効と判定されたURLがスキップまたはフラグ立てられているか確認する
18. エラーが発生した場合は、スクリプトのログに従い修正を行う（CSVパスミス、ネットワークタイムアウト等）
19. 都道府県レジストリ用の `data/prefecture_urls.csv` が存在しない場合は、手作業で作成するか、別スクリプトで生成する
20. 市区町村レジストリ用の `data/city_urls.csv` が存在しない場合は、同様に準備する（上位都市から優先的に）
21. レジストリと同期スクリプトが正常に動作したら、定期実行のための cron またはスケジューラー設定案をドキュメントに記載する
22. 完了したら、`docs/` または `README.md` に実装手順を記録する
23. バージョン管理のため、新規作成したレジストリモジュールとスクリプトをGitに追加する
24. 次のステップ（ベースクローラーのカテゴリ・優先度フィルタリング強化）に進む準備ができたことを確認する