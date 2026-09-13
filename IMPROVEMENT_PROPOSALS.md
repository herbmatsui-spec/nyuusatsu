# 改善案：全国カバー率向上のための9つの優先順位付き提案

## 優先順位1: 都道府県マスタデータの投入
`scripts/seed_prefectures.py` または `scripts/create_tables_and_seed_prefectures.py` を実行し、`prefectures` テーブルと `agencies` テーブに47都道府県のデータを投入する。これが都道府県レベルでのクロールの基盤となる。

## 優先順位2: 国政府庁マスタデータの投入
`scripts/import_ministries.py` を実行し、`agencies` テーブルに中央省庁のデータを投入する。これによりGEPS等の国家機関入札サイトへの対応が可能になる。

## 優先順位3: 市区町村マスタデータの準備と投入
`scripts/fetch_municipality_codes.py` と `scripts/prepare_municipality_codes.py` を使用して全国地方公共団体コードのフルリストを取得し、`scripts/import_agencies.py` などを経由して `agencies` テーブルに市区町村データを投入する（最初は人口上位の自治体から優先的に）。

## 優先順位4: 都道府県別クローラ設定ファイルの一括生成
`scripts/generate_prefecture_configs.py` を実行し、`crawler/parsers/agency_config/prefectures/` ディレクトリに47都道府県それぞれのJSON設定ファイルを生成する。これにより各都道府県の入札サイトに特化したクロールが可能になる。

## 優先順位5: 高優先度市区町村向け設定ファイルの生成
市区町村データに基づき、人口10万以上等の高優先度自治体向けに設定ファイルを生成するスクリプトを作成・実行する。まずは主要都市から段階的にカバー率を高める。

## 優先順位6: URLレジストリと同期システムの実装
Phase 3の仕様に従い、`crawler/registry/` モジュールを実装し、`scripts/sync_registry_to_db.py` を走らせて `agencies` テーブルの `base_url` と `bid_url_pattern` フィールドを設定ファイルやマスタデータから自動更新する。

## 優先順位7: ベースクローラーのカテゴリ・優先度フィルタリング強化
`crawler/base_crawler.py` と `crawler/generic_crawler.py` を改修し、データベースの `category_id` と `priority_level` フィールドを参照してクロール対象をフィルタリングできるようにする。これにより「都道府県のみ」「優先度高のみ」等の選択的クロールが可能になる。

## 優先順位8: サイト構造自動検出とセレクタ生成機能の導入
`crawler/parsers/structure_detector.py`、`crawler/parsers/selector_generator.py` 等を実装し、未知のサイト構造に対して自動で最適なセレクタを生成する仕組みを導入する。これにより設定ファイルの手動作成負荷を大幅に削減できる。

## 優先順位9: クロール頻度の動的調整とモニタリングシステム
`database/models/crawler_schedule.py` テーブルを作成し、`scripts/adjust_crawl_frequency.py` を実装して過去のクロール成功率や更新頻度に基づいてクロール間隔を動的に調整する。また、カテゴリ・優先度別の成功率レポートを定期生成し、改善の優先順位付けに活用する。