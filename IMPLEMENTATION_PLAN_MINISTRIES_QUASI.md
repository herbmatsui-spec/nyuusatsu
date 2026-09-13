# 国政府庁・外郭団体のマスタデータ整備および専用レジストリの追加
## ステップ 1-24

1. `data/master_ministries.csv` が存在することを確認し、カラム構成（agency_name, municipality_code, priority_level）を確認する（既に存在）。
2. `data/master_quasi_agencies.csv` が存在するか確認する。存在しない場合は、主要外郭団体のリストを手作業でまとめCSVを作成する（フォーマット: agency_name, municipality_code（空可）, priority_level）。
3. `agency_categories` テーブルに「国」および「外郭団体」カテゴリが登録されていることを確認する（既に存在）。無ければ `scripts/init_categories.py` を実行して追加する。
4. `agencies` テーブルに `category_id` 外部キーが設定されていることを確認し、必要に応じてインデックスを追加する（既に存在）。
5. 省庁用レジストリモジュール `crawler/registry/ministry_registry.py` を作成する。基底クラス `BaseRegistry` を継承し、`master_ministries.csv` を読み込み、`RegistryRecord` を生成する。
6. `crawler/registry/ministry_registry.py` 内で、`base_url` と `bid_url_pattern` を生成するロジックを実装する。例：
   - `base_url`: `https://www.mlit.go.jp/` など省庁ごとの固定ドメインがない場合は、`https://www.go.jp/` の共通ドメインを使用するか、空にする。
   - `bid_url_pattern`: GEPS 検索 URLを生成する。例: `https://search.geps.go.jp/search?q={agency_name}`（URLエンコード）。より詳細には、省庁コードがある場合は `&org={code}` を追加するが、現状コード不明のため名前のみで検索する。
7. 外郭団体用レジストリモジュール `crawler/registry/quasi_agency_registry.py` を作成する。同様に `BaseRegistry` を継承し、`master_quasi_agencies.csv` を読み込む。
8. `crawler/registry/quasi_agency_registry.py` 内で、`base_url` と `bid_url_pattern` を生成するロジックを実装する。例：
   - `base_url`: 外郭団体の公式ウェブサイトURLが分かっている場合はCSVから読み取り、分からない場合は空にする（後で手動追加）。
   - `bid_url_pattern`: 入札情報ページのパターンが分かっている場合は同様に設定し、分からない場合は GEPS 検索 URLをフォールバックとする。
9. `crawler/registry/__init__.py` に新しいレジストリクラスをインポートし、`REGISTRY_FACTORIES` 辞書に追加するための準備を行う（ただし `REGISTRY_FACTORIES` は `scripts/sync_registry_to_db.py` 内に定義されているため、そちらを修正する）。
10. `scripts/sync_registry_to_db.py` の `REGISTRY_FACTORIES` 辞書に `"ministry": MinistryRegistry`、`"quasi": QuasiAgencyRegistry` を追加する。
11. `scripts/sync_registry_to_db.py` の `CATEGORY_NAME_MAP` 辞書に `"ministry": "国"`、`"quasi": "外郭団体"` を追加する。
12. スクリプト実行前にバックアップを取得する（例: `cp bids_system.db bids_system.db.backup_pre_sync2`）。
13. まずは省庁レジストリのみでテスト実行を行う：`python scripts/sync_registry_to_db.py --type ministry` を実行し、ログを確認する。
14. テスト実行後に、`sqlite3 bids_system.db "SELECT name, base_url, bid_url_pattern FROM agencies WHERE category_id = (SELECT id FROM agency_categories WHERE name='国') LIMIT 5;"` を実行し、両カラムが更新されているか確認する。
15. エラーがないことを確認し、問題があればスクリプトまたはレジストリを修正する（例: カラム名ミス、NULLハンドリング等）。
16. 省庁レジストリについて全件同期を実行する：`python scripts/sync_registry_to_db.py --type ministry` を実行する。
17. 同期完了後に、省庁の `base_url` と `bid_url_pattern` が設定されている件数を確認する（期待: master_ministries.csv の行数-1 ヘッダー分）。
18. 次に、外郭団体レジストリについて同様にテスト実行を行う：`python scripts/sync_registry_to_db.py --type quasi` を実行し、結果を確認する。
19. 外郭団体レジストリについて全件同期を実行する：`python scripts/sync_registry_to_db.py --type quasi` を実行する。
20. 同期完了後に、外郭団体の `base_url` と `bid_url_pattern` が設定されている件数を確認する（期待: master_quasi_agencies.csv の行数-1 ヘッダー分。データが不足している場合はテンプレートまたはフォールバックで生成する）。
21. 外郭団体についてURLデータが不足していることを考慮し、一時的にテンプレートベースでURLを生成するフォールバックロジックを `crawler/registry/quasi_agency_registry.py` に追加する（例: JISコードがないため、`https://www.{name}.go.jp/` のような推測URLまたは空にする）。
22. 全外郭団体について、テンプレートを用いたURLレジストリ同期を実行する：`python scripts/sync_registry_to_db.py --type quasi` を実行する。
23. 同期完了後に、`sqlite3 bids_system.db "SELECT COUNT(*) FROM agencies WHERE base_url IS NOT NULL AND base_url != '' AND bid_url_pattern IS NOT NULL AND bid_url_pattern != '' AND category_id IN (SELECT id FROM agency_categories WHERE name IN ('国','外郭団体'));"` を実行し、両カラムが設定されている agencies の件数を確認する。目標は国庁分＋外郭団体分となる。
24. 完了したら、`docs/` または `README.md` に実施手順と結果を記録し、次のステップ（全体統合テスト）に進む準備ができたことを確認する。

