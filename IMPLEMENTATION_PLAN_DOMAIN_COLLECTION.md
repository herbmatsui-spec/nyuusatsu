# 国政府庁・外郭団体のドメインデータ収集のための改善案実装計画書
## ステップ 1-24

### フェーズ1: 手動収集によるベースライン構築 (ステップ 1-8)

1. 国政府庁の公式ウェブサイトドメインリストを手作業で調査し、CSV ファイル `data/manual_ministry_domains.csv` を作成する（フォーマット: agency_name, base_url, 注釈）。
2. 主要な外郭団体について同様に調査し、`data/manual_quasi_domains.csv` を作成する。
3. 各 CSV ファイルにヘッダー行を含め、エンコーディングは UTF-8 とする。
4. 作成した CSV ファイルを Git リポジトリに追加し、変更をコミットする（例: "chore: add manual domain CSV for ministries and quasi agencies"）。
5. `crawler/registry/` ディレクトリに新しいレジストリモジュール `manual_ministry_registry.py` と `manual_quasi_registry.py` を作成し、`BaseRegistry` を継承する。
6. 各レジストリは対応する CSV を読み込み、`RegistryRecord` を生成する際に `base_url` を CSV から、`bid_url_pattern` は GEPS 検索 URLをフォールバックとして設定する（すでに bid_url_pattern が設定されている場合はそれを優先）。
7. `crawler/registry/__init__.py` に新しいレジストリクラスをインポートし、`REGISTRY_FACTORIES` に手動レジストリを追加するための準備を行う（ただし `REGISTRY_FACTORIES` は `scripts/sync_registry_to_db.py` 内にあるため、そちらを後ほど修正する）。
8. `scripts/sync_registry_to_db.py` の `REGISTRY_FACTORIES` 辞書に `"manual_ministry": ManualMinistryRegistry`、`"manual_quasi": ManualQuasiRegistry` を追加し、`CATEGORY_NAME_MAP` に `"manual_ministry": "国"`、`"manual_quasi": "外郭団体"` を追加する（既存の ministry/quasi レジストリと区別するため、一旦別種別とする）。

### フェーズ2: ルールベースドメイン推定による自動生成 (ステップ 9-12)

9. 国政府庁および外郭団体の組織名からドメインを推定するヒューリスティック関数を含むユーティリティモジュール `crawler/utils/domain_estimator.py` を作成する。
10. 主な推定ルール：
    - 組織名のアルファベット表記（例: "METI"）を取得し、小文字に変換して `.go.jp` を付与（例: `meti.go.jp`）。
    - 和名がある場合は、ローマ字変換ライブラリ（例: pykakasi）を使用してアルファベット表記を取得し、同様に `.go.jp` または `.or.jp` を付与する。
    - 特殊ケース（例: "総務省" → `soumu.go.jp`、"環境省" → `env.go.jp`）については辞書マッピングを用意する。
11. `crawler/registry/` に推定ベースのレジストリモジュール `estimated_ministry_registry.py` と `estimated_quasi_registry.py` を作成し、`BaseRegistry` を継承する。
12. これらのレジストリはマスタ CSV（`master_ministries.csv`, `master_quasi_agencies.csv`）を読み込み、`domain_estimator.estimate_base_url(name)` で `base_url` を生成し、`bid_url_pattern` は GEPS 検索 URL をフォールバックとする。生成結果をログに出力して検証可能にする。

### フェーズ3: GEPS およびウェブクロールによる自動発見 (ステップ 13-18)

13. GEPS 検索結果から各省庁・外郭団体の独自入札システム URL を発見するスクリプト `scripts/discover_domain_from_geps.py` を作成する。
14. スクリプトは、マスタ CSV の組織名をキーワードとして GEPS 検索 API（または HTML スクレイピング）を呼び出し、上位結果からドメインを抽出する。
15. 抽出ロジック：
    - 検索結果ページからリンク URL を収集し、同じホスト名が複数回出現するものを候補とする。
    - ホスト名が `.go.jp` または `.or.jp` で終わるものを優遇し、またパスに `bid`, `chushou`, `keiyaku` 等のキーワードを含むものをさらに優遇する。
16. 発見されたドメインを一時 CSV `data/discovered_ministry_domains.csv` と `data/discovered_quasi_domains.csv` に出力する（フォーマット: agency_name, discovered_base_url, confidence_score）。
17. 人間によるレビュー用の簡易ビューアスクリプト `scripts/review_discovered_domains.py` を作成し、CSV を読み込んで一覧表示し、ユーザーが YES/NO で承認または修正できるようにする。
18. 承認されたドメインをマスタ CSV にマージするスクリプト `scripts/merge_discovered_domains.py` を作成し、`base_url` カラムを更新する（空の場合のみ上書きするか、ユーザーが指定した優先度で決定する）。

### フェーズ4: 官公庁リンク集および業界団体からの一括取得 (ステップ 19-22)

19. 国土交通省が提供する「官公庁ホームページリンク集」や総務省の「政府情報公開システム」等の公開リンク集から URL を一括取得するスクリプト `scripts/fetch_government_link_lists.py` を作成する。
20. スクリプトはリンク集ページをスクレイピングし、`<a>` タグの `href` を抽出し、ドメイン名を抽出して CSV に蓄積する。
21. 抽出結果をフィルタリングし、省庁・外郭団体名と fuzzy マッチング（例: レーベンシュタイン距離）を行い、組織名と URL の対応関係を推定する。
22. 推定結果を人間レビュー用 CSV に出力し、フェーズ3のレビュースクリプトで同様にレビュー後にマスタにマージする。

### フェーズ5: 最終統合およびシステムへの反映 (ステップ 23-24)

23. すべてのソース（手動収集、ルールベース推定、GEPS発見、リンク集収集）から得られたドメイン情報を優先順位付きでマスタ CSV に統合するスクリプト `scripts/integrate_all_domains.py` を作成する。
    - 優先順位： 1) 手動収集 2) 人間レビュー承認済み自動発見 3) ルールベース推定 4) リンク集推定
    - 同一組織に複数ソースがある場合は優先順位が高い方を採用し、競合がある場合は警告を出す。
24. 統合後のマスタ CSV を用いて `scripts/sync_registry_to_db.py` を実行し（レジストリタイプ `ministry` と `quasi` を使用）、`agencies` テーブルの `base_url` と `bid_url_pattern` を最終更新する。実行結果をログに出力し、`docs/` または `README.md` に実施手順と結果を記録する。

EOF