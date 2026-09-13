# URLレジストリと同期システムを実装し、agencyのbase_url/bid_patternを自動更新する（完全版）
## ステップ 1-24

1. 現在の `agencies` テーブルのスキーマを確認し、`bid_url_pattern` カラムが存在しないことを確認する（既に実施済み）。
2. `alembic` マイグレーションスクリプトを作成し、`agencies` テーブルに `bid_url_pattern VARCHAR` カラムを追加する（例: `alembic/revisions/add_bid_url_pattern_to_agencies.py`）。
3. マイグレーションスクリプトの中で、既存の `base_url` カラムに `NOT NULL` 制約がないことを確認し、必要に応じて制約を調整する（ただしここでは変更しない）。
4. 生成されたマイグレーションスクリプトを確認し、SQL構文が正しいか目視チェックする。
5. `alembic upgrade head` を実行してマイグレーションを適用する。
6. マイグレーション適用後、`sqlite3 bids_system.db ".schema agencies"` を実行し、`bid_url_pattern` カラムが追加されていることを確認する。
7. `crawler/registry/` ディレクトリ内のレジストリモジュール（`prefecture_registry.py`, `city_registry.py`, `municipality_registry.py`）を確認し、`search_url` または `bid_url_pattern` に相当する情報を取得できるか確認する。
8. 必要に応じて、レジストリモジュールを修正し、取得したURL情報を `base_url` と `bid_url_pattern` の両方として返すメソッドを追加する（例: `get_base_url_and_pattern(agency_code)`）。
9. `scripts/sync_registry_to_db.py` を確認し、現在のところ `base_url` しか更新していないか、`search_url` への更新しか行っていないかを確認する。
10. スクリプトを修正し、レジストリから取得した `base_url` と `bid_url_pattern` （または同等の情報）を用いて、`agencies` テーブルの両カラムをアップデートするようにする（UPSERTまたはUPDATE）。
11. スクリプト実行前に、バックアップを取得する（例: `cp bids_system.db bids_system.db.backup_pre_sync`）。
12. まずは都道府県レジストリのみでテスト実行を行う：`python scripts/sync_registry_to_db.py --type prefecture --limit 5` （もしくは同等の引数）を実行し、ログを確認する。
13. テスト実行後に、`sqlite3 bids_system.db "SELECT name, base_url, bid_url_pattern FROM agencies WHERE category_id = (SELECT id FROM agency_categories WHERE name='都道府県') LIMIT 5;"` を実行し、両カラムが更新されているか確認する。
14. エラーがないことを確認し、問題があればスクリプトを修正する（例: カラム名ミス、NULLハンドリング等）。
15. 都道府県レジストリについて全件同期を実行する：`python scripts/sync_registry_to_db.py --type prefecture` を実行する。
16. 同期完了後に、都道府県の `base_url` と `bid_url_pattern` が設定されている件数を確認する（期待: 47 件両方）。
17. 次に、市区町村レジストリ（上位都市分）について同様にテスト実行を行う：`python scripts/sync_registry_to_db.py --type city --limit 5` を実行し、結果を確認する。
18. 市区町村レジストリについて全件同期を実行する：`python scripts/sync_registry_to_db.py --type city` を実行する。
19. 同期完了後に、市区町村の `base_url` と `bid_url_pattern` が設定されている件数を確認する（期待: city_urls.csv の行数-1 ヘッダー分）。
20. 全市区町村についてURLデータが不足していることを考慮し、一時的にテンプレートベースでURLを生成するスクリプトを作成する（例: `scripts/generate_municipality_url_templates.py`）。このスクリプトは、`data/municipalities.csv` を読み込み、市町村コードから決まったパターン（例: `https://www.pref.[code].jp/bid/`）を生成し、`crawler/registry/municipality_registry.py` が参照できる一時的なCSVまたはメモリ内データを提供する。
21. テンプレートスクリプトを作成し、動作確認のためにいくつかサンプル出力を表示する。
22. `municipality_registry.py` を修正し、既存の `data/municipality_urls.csv` が存在しない場合はテンプレートスクリプトからデータを取得するフォールバックロジックを追加する。
23. 全市区町村（1700+）について、テンプレートを用いたURLレジストリ同期を実行する：`python scripts/sync_registry_to_db.py --type municipality` を実行する（または `--type all`）。
24. 同期完了後に、`sqlite3 bids_system.db "SELECT COUNT(*) FROM agencies WHERE base_url IS NOT NULL AND base_url != '' AND bid_url_pattern IS NOT NULL AND bid_url_pattern != '';"` を実行し、両カラムが設定されている agencies の件数を確認する。目標は都道府県47＋市区町村上位分＋テンプレートでカバーできた分となる。完了したら、`docs/` または `README.md` に実施手順と結果を記録する。