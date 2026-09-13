# URLレジストリ同期 (URL Registry Sync)

## 概要
`crawler/registry/` が管理する都道府県・市区町村の URL レジストリを
`agencies` テーブルの `base_url` と `url_registry` テーブルの
`base_url` / `search_url`（入札URLパターン）へ同期します。

## 利用可能なレジストリ種別
| 種別 | 読み込み元 CSV | 備考 |
|---|---|---|
| `prefecture` | `data/prefecture_urls.csv` | 全47都道府県 (category_id=2, system_type=自治体共通) |
| `city` | `data/city_urls.csv` | 指定都市・中核市・特別区 (category_id=3, system_type=自治体独自) |
| `municipality` | `data/master/municipality_codes.csv` | マスタ補完 + JISコードテンプレート生成 |

`city` / `municipality` は未設定の場合テンプレートからURLを生成します
(GEPS検索URLをbid_url_patternとして利用)。

## CSV再生成
```
python scripts/generate_url_registry_csvs.py
```
`data/master/municipality_codes.csv` から `data/prefecture_urls.csv` と
`data/city_urls.csv` を再生成します。

## 同期実行
```
# 都道府県のみ同期
python scripts/sync_registry_to_db.py --type prefecture

# 未設定(base_url空)のみ更新
python scripts/sync_registry_to_db.py --type prefecture --only-unset

# URLバリデーション(HEAD→GET)を伴って同期
python scripts/sync_registry_to_db.py --type prefecture --validate

# 全レジストリ同期 (dry-run)
python scripts/sync_registry_to_db.py --type all --dry-run
```

## オプション
- `--type {prefecture,city,municipality,all}` (default: `prefecture`)
- `--registry-path PATH` : CSVパスを個別指定
- `--dry-run` : DB書き込みなしプレビュー
- `--only-unset` : `base_url` が空のレコードのみ更新
- `--validate` : `crawler/registry/url_validator.py` で到達性を判定

## URL変更検知
`crawler/registry/url_change_detector.py` はスナップショット
(`data/url_snapshots.json`) とレスポンスハッシュを比較し、ステータスコード
変更・コンテンツ変更を検知します。

## 定期実行 (cron)
```
# 毎日午前2時に都道府県レジストリを同期し、未設定のみ更新
0 2 * * * cd /path/to/nyuusatsu && python scripts/sync_registry_to_db.py --type prefecture --only-unset >> logs/registry_sync.log 2>&1

# 毎週月曜日午前3時に市区町村を同期
0 3 * * 1 cd /path/to/nyuusatsu && python scripts/sync_registry_to_db.py --type city --only-unset >> logs/registry_sync.log 2>&1
```
Docker/Airflow で運用する場合は `DATABASE_URL` を環境変数に設定してください。
