# 改善案08: 承認済み公式データによる収集設定の品質改善

## 2026-09-17 旧計画の評価（実ソース再確認）

旧計画は存在しない配置を前提にし、実装済み機能の再作成、無根拠の機関数目標、週次の自動上書き・実クロールを混在させていた。今回は既知の承認済み公式データをオフラインで検証して設定候補を作るMVPへ限定する。登録数・URL保有数・到達確認数・抽出成功数は別の指標とする。

|区分|実ソースの根拠|判断|
|---|---|---|
|配置と生成機能は既存|`scripts/gen_crawler.py:50-79` が設定辞書、`:86-95` が共通クローラーを使う薄いPython生成、`:98-128` がregistry入力|`crawler/gen_crawler.py` を新設しない。現在の共通実装を維持する。|
|旧調査から改善済み|`scripts/gen_crawler.py:16` は正しい共通charset実装をimport、`:66` は入力URLを保持、`:120-122` は全候補をdry-run表示|以前の「存在しないimport」「/list.html推測」「先頭5件だけ」の欠陥を再修正しない。回帰テストへ置換する。|
|不足|`scripts/gen_crawler.py:113` はunverifiedを付与するが、`:126` / `:162` はwrite_textで出力|未承認候補の実行防止、既存ファイルの上書き防止、候補と有効設定の分離が必要。|
|集計は既存|`scripts/list_registered_agencies.py:111-137` はURL状態を分離、`:140-175` は重複をまとめて集計|集計スクリプトを再作成しない。`:35-39` の概数を全国網羅率の確定分母として使わない。|
|公式入力パーサーは既存|`crawler/utils/registry_scraper.py:67-71` はローカルファイルのみ、`:93-119` はprovenanceとunverifiedを付与、`:121` はCSV処理|任意ドメイン発見やネットワーク自動探索を追加せず、承認された資料の取り込みを使う。|
|階層は既存|`crawler/registry/__init__.py:21-44` のidentityとparent_id|一律にparent_id migrationを追加しない。既存コード・親子関係の整合性を検証する。|
|正規化に問題|`crawler/utils/registry_scraper.py:312-319` は企業名normalizerで機関名・親IDを変換|発注機関に企業名辞書を流用しない。原表記・公式コードを保存し、曖昧な統合を保留する。|
|待機・再試行は既存|`crawler/base_crawler.py:94` のRateLimiter、`crawler/config_driven_crawler.py:141-182` の取得/再試行、`crawler/utils/rate_limiter.py:35-50` のドメイン待機|同じretry実装を追加しない。ただし全対象ドメインのrobots判定と複数インスタンスの共有制限は別途保証が必要。|
|未確認の旧計画パス|`scripts/validate_crawler_config.py` と `crawler/utils/politeness_policy.py` は今回の確認で存在しない|必要な新設分だけ「新規予定」と明示する。旧計画のscheduler.py、crawler/configへの配置を決め打ちしない。|

## 範囲・非目標・依存関係

- 今回編集するのは本計画書のみ。以下は将来の実装手順。実DB読取・migration・クロール・設定有効化・scheduler起動・外部通知を自動実行しない。
- 入力は提供済み/手動承認済みの公式資料のローカルコピーと既知のURLのみ。承認元・取得日・資料ハッシュ・対象範囲を記録する。公式性や到達性をファイル名/URL文字列から推測しない。
- 出力はレビュー用候補と品質結果。新規ファイルは `scripts/validate_crawler_config.py`、`crawler/utils/politeness_policy.py`、`tests/unit/test_crawler_config_validation.py`、`tests/unit/test_politeness_policy.py`（すべて新規予定）。その他の列挙パスは既存を再利用する。候補データはテスト中tmp_pathだけへ出す。
- 非目標: 任意ドメイン自動発見、一般Web探索、JSブラウザー追加、robots無視、未確認URLの推測、企業辞書による機関名統合、週次自動適用、全国一括収集、800万件の約束・国内最大級の広告、階層DB再設計、通知基盤の新設。
- 02が通知/outbox、04が管理者アクセス範囲を担当する。08は新しい通知送信や課金権限を実装しない。ユーザー向け集計を将来公開する際は04のscopeをcount/aggregate前に適用し、user/org・policy versionでキャッシュを分ける。本MVPはオフラインの管理用候補評価のみ。
- 01/06の検索フィールド名・都道府県2桁文字列を壊さない。予算のraw税区分を推測しない。取得件数から03の応札分母や09の勝率を作らない。ProcurementForecastは調達見通しであり勝率予測ではない。
- 前提は既存registry/parser/generatorの契約確認と、承認済み資料を所有者が準備できること。未準備ならfixtureだけで開発し、実ソース追加は保留する。
- 総工数目安: **38時間（実装・隔離テスト込み、実資料の収集/承認待ち・実運用試験は除外）**。各ステップ4時間以内。

## テスト実行前の必須条件

`tests/conftest.py:12-21` が永続 `tests/fixtures/test.db` を初期化するため、通常のpytestを直接実行しない。ステップ1でローカルfixture、tmp_path、注入session、fake HTTP/clock/sleepを用意し、ネットワークと `.env` 読込を遮断する。`--noconftest` は対象テストの全fixtureが自立していることを確認した場合のみ。本番registry、生成先、DB、robotsサーバーにもアクセスしない。

### ステップ 1: オフライン検証環境を固定
- **対象**: `tests/unit/test_gen_crawler.py`、`tests/unit/test_registry_scraper.py`、`tests/unit/test_config_driven_crawler.py`（既存・再利用）。`tests/conftest.py`（既存・参照のみ）。
- **作業**:
  1. 対象テストとimportを読み、既定のdata/config/DB/HTTPを使う箇所を列挙する。
  2. registry factoryと出力先をfake/tmp_pathへ置換し、通信呼出しと `.env` 読込を検知したら失敗させる。
  3. 公式資料を模したCSV3行、HTML2ページ、文字コード3種、時刻固定のfixtureをテスト内に定義する。
- **確認**: fixture生成先はtmp_pathのみ。既存のdata/configのハッシュが変わらず、HTTP・DB・メール呼出し回数は0。入力ファイルなしは明示エラーとなる。
- **完了条件**: generatorのCLIを実データで起動せずに純粋関数とfake取得の検証が可能。
- **工数目安**: 3時間（依存確認1、fixture1、検証1）。

### ステップ 2: 登録と収集成功の分母を分離
- **対象**: `scripts/list_registered_agencies.py`、`tests/unit/test_gen_crawler.py`（既存・再利用）。
- **作業**:
  1. `_report/summarize` の既存状態分類を維持し、承認された一覧の件数と概数目標を別項目にする。
  2. 到達確認済みでも抽出確認済みではないと明示し、抽出結果の有無を独立して扱う。
  3. 分母資料の日時・範囲がない場合は網羅率をnullとし、重複登録を分子に足さない。
- **確認**: 公式一覧3機関、登録4行（同一コード重複1）、verified URL1件なら登録ユニーク3・到達確認1。抽出結果なしは成功0でなく未検証。分母なしで網羅率null。
- **完了条件**: 登録数を成功数として宣伝せず、概数TARGETSから全国網羅率を生成しない。
- **工数目安**: 3時間（指標1、集計1、テスト1）。

### ステップ 3: 承認された公式資料だけを取り込む
- **対象**: `crawler/utils/registry_scraper.py`、`tests/unit/test_registry_scraper.py`（既存・再利用）。
- **作業**:
  1. 既存sources/provenance形式に承認者・承認日・元資料ハッシュ・対象機関範囲を保持する入力検証を加える。
  2. `_fetch` のローカル限定を維持し、URLを入力しただけでは取得を開始しない。
  3. 未承認・ハッシュ不一致・必須列欠落を候補不採用として理由付きで返す。
- **確認**: 承認済みCSV3行から3候補が出る。同じCSVを1文字変更したらハッシュ不一致で採用0。URLだけ/承認日なしは取得0回かつ未承認。provenanceの行番号が各候補に残る。
- **完了条件**: データの公式性・承認・出典を追跡でき、外部探索へ自動フォールバックしない。
- **工数目安**: 3時間（入力契約1、検証1、テスト1）。

### ステップ 4: 機関名と階層を壊さない重複検査
- **対象**: `crawler/utils/registry_scraper.py`、`crawler/registry/__init__.py`、`tests/unit/test_registry_hierarchy.py`、`tests/unit/test_registry_scraper.py`（既存・再利用）。
- **作業**:
  1. `deduplicate_and_normalize` から企業用normalizerによる機関名変換を外し、原名と公式コードを保存する。
  2. 比較用文字列の処理は前後空白除去に限定し、コード一致を優先、コードなしの同名は同一親かつ出典で確認できる場合だけ統合する。
  3. 親未登録・自己参照・循環を検査し、不明な親を推測せず保留する。
  4. 競合するURL/コードは最新行で上書きせず両候補と理由を返す。
- **確認**: 同名の「中央区」が別コードなら2件。同コードの同一資料重複は1件。A→B→Aは循環エラー。「県」を削除したり銀行名へ法人格を補ったりしない。
- **完了条件**: 原名・identity・親関係が追跡でき、既存parent_idを再設計しない。
- **工数目安**: 4時間（名前1、重複1、階層1、テスト1）。

### ステップ 5: 既存generatorの回帰保護
- **対象**: `scripts/gen_crawler.py`、`crawler/config_driven_crawler.py`、`tests/unit/test_gen_crawler.py`（既存・再利用）。
- **作業**:
  1. 現在の共通charset import、入力URL保持、薄いFetcher生成をテストで固定する。
  2. registry由来候補は承認情報を引き継ぐが、初期状態は未検証/無効として出力する。
  3. 同名機関や同名の安全化ファイル名が衝突した場合に上書きせず、identity由来の区別を維持する。
- **確認**: fixtureの既知URLは完全一致で保持され `/list.html` が追加されない。生成PythonのASTが解析可能でimport先は共通クローラー。6候補dry-runで6設定が出力されファイル作成0。
- **完了条件**: 改善済み生成処理を作り直さず、候補が勝手に有効化されない。
- **工数目安**: 3時間（回帰1、メタ情報1、テスト1）。

### ステップ 6: 設定構文と承認状態を検証
- **対象**: `scripts/validate_crawler_config.py`、`tests/unit/test_crawler_config_validation.py`（新規予定）。`scripts/gen_crawler.py`、`crawler/config_driven_crawler.py`（既存・再利用）。
- **作業**:
  1. 既存parserのキーを読み、`list_url/list_item_selector/detail_fields/pagination/crawl_settings` を実契約として検証する純粋関数を作る。
  2. URL・selector構文・max_pages/timeout/delay/retryの有限な上限下限を検査し、未知キーはエラーにする。
  3. 「構文有効」と「承認/robots/抽出確認済み」を別判定にし、結果をキー名と理由付きで返す。
- **確認**: `list_item_selector="["` は構文エラー、max_pages=0/負数は拒否、未承認の正常YAMLは構文有効だが実行不可。必須キー欠落で対象キー名が表示される。
- **完了条件**: 存在しないtitle_selectorを一律要求せず、検証の成功だけでは有効設定へ昇格しない。
- **工数目安**: 3時間（キー検証1、状態分離1、テスト1）。

### ステップ 7: 全対象ドメインの利用条件と速度制限
- **対象**: `crawler/utils/politeness_policy.py`、`tests/unit/test_politeness_policy.py`（新規予定）。`crawler/utils/rate_limiter.py`、`crawler/config_driven_crawler.py`（既存・再利用）。
- **作業**:
  1. 承認済みドメイン集合・取得済みrobots情報・User-Agent・連絡先・時刻を注入する判定関数を作り、未知/期限切れ/取得失敗は拒否する。
  2. 全ドメインについてrobotsの禁止パスとCrawl-delayを評価し、許可ドメインであっても免除しない。
  3. 既存RateLimiterを共有して複数インスタンスにも最も厳しい待機を適用し、MVPの実行方式は同一共有制御下の単一workerに限定する。
  4. redirect先・詳細・PDF・robots取得を含む全リクエストに承認と待機を適用する。fake client/clockだけで接続を検査する。
- **確認**: 承認済みでもDisallow対象はHTTP0回。robots不明/期限切れは停止。設定3秒・Crawl-delay10秒なら同domainの2要求間隔はfake時計で10秒以上。別domainへのredirectは未承認なら追跡しない。
- **完了条件**: 政府ドメインだけを例外扱いせず、複数worker運用は共有制御の別評価完了まで禁止する。
- **工数目安**: 4時間（判定1、robots1、共有待機1、テスト1）。

### ステップ 8: 候補出力と有効設定を分離
- **対象**: `scripts/gen_crawler.py`、`scripts/validate_crawler_config.py`（新規予定）、`tests/unit/test_gen_crawler.py`（既存・再利用）。
- **作業**:
  1. 全候補のdry-runを既定の安全経路とし、書込は明示指定された候補用ディレクトリだけに制限する。
  2. 同名ファイルが既存なら差分・ハッシュを報告して停止し、通常操作で上書きしない。
  3. 構文・承認・利用条件・抽出fixtureの各結果を候補に結び付ける。有効設定への適用は別途手動承認とし、本MVPに自動適用コードを追加しない。
- **確認**: tmp_pathに既存設定Aを置き再生成してもAのハッシュ不変。6候補のdry-run結果は6件。1件検証失敗なら失敗候補は不採用で、有効設定の変更0件。
- **完了条件**: 候補の生成成功と本番適用を分離し、既存の手調整selectorを保護する。
- **工数目安**: 3時間（出力制限1、衝突処理1、テスト1）。

### ステップ 9: HTML抽出の最小fixture評価
- **対象**: `tests/unit/test_config_driven_crawler.py`、`tests/unit/test_gen_crawler.py`、`crawler/config_driven_crawler.py`（既存・再利用）。
- **作業**:
  1. 承認済みソースを模した一覧2ページ・詳細2件・PDFリンク1件をfake応答として構成する。
  2. UTF-8/CP932/EUC-JPを入力し、日本語タイトルと日付・相対URL解決を検査する。
  3. 次ページ循環・同一リンク重複・上限到達・selector不一致を検査し、不一致は成功0件でなく要確認として返す。
- **確認**: 2ページ内の同一URL重複を除いて詳細2件・PDFリンク1件。3文字コードすべてで「橋梁補修」が一致。max_pages=2なら3ページ目要求0回。循環は停止する。
- **完了条件**: 生成された構文が実fixtureにも適合し、実ページ取得・PDFダウンロードはしない。
- **工数目安**: 4時間（ページ1、文字コード1、停止条件1、テスト1）。

### ステップ 10: 既存retryと失敗分類を検証
- **対象**: `crawler/config_driven_crawler.py`、`crawler/base_crawler.py`、`tests/unit/test_config_driven_crawler.py`（既存・再利用）。
- **作業**:
  1. 再試行箇所を一つに定め、基底と子クラスの二重retryを起こさないよう既存経路を整理する。
  2. 403/404は停止、429はRetry-Afterと上限を尊重、5xx/timeoutは最大3試行のfixtureを追加する。
  3. 利用条件拒否・通信失敗・構文不良・抽出不一致を別状態で返し、自動再開しない。
- **確認**: fake 503→503→200は要求3回、403は1回、robots拒否は0回。timeout連続は3回で停止。Retry-After60秒はfake時計で60秒未満に再試行しない。実sleepは0回。
- **完了条件**: 通知やDBの停止フラグを新設せず、有限な再試行と原因がレビュー可能になる。
- **工数目安**: 3時間（経路1、分類1、テスト1）。

### ステップ 11: 品質基準と段階的導入ゲート
- **対象**: `scripts/list_registered_agencies.py`、`scripts/validate_crawler_config.py`（新規予定）、本計画書（既存・再利用）。
- **作業**:
  1. 入力機関数、承認候補数、構文合格数、利用条件確認数、fixture抽出合格数を別々に集計する。
  2. fixtureに既知の正解を付け、期待リンク漏れ0・無関係リンク混入0・タイトル/日付欠落0を候補採用条件にする。
  3. 将来の実運用は管理者が少数の明示機関を選び、件数/頻度/時間上限と停止責任者を承認してから別作業で行うと記録する。
- **確認**: 候補3件で構文合格3・robots確認2・抽出合格1なら採用可能は全条件を満たす1件のみ。分母未知はnull。上位20%などの自動拡大は発生しない。
- **完了条件**: 合格基準と停止基準が定量化され、実クロール・scheduler登録・広告指標の更新が残作業へ混入しない。
- **工数目安**: 2時間（集計1、ゲート確認1）。

### ステップ 12: 受入検査と切り戻し
- **対象**: 上記既存テストと新規予定テスト、本計画書（既存・再利用）。
- **作業**:
  1. ステップ1の隔離を確認後、generator/registry/parser/validation/policyのテストを限定実行する。自立fixture確認済みの場合のみ `pytest --noconftest tests/unit/test_gen_crawler.py tests/unit/test_registry_scraper.py tests/unit/test_registry_hierarchy.py tests/unit/test_config_driven_crawler.py tests/unit/test_crawler_config_validation.py tests/unit/test_politeness_policy.py` を使う。
  2. `.github/workflows/test.yml:18-20` の `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`、`mypy .` を実行可能な環境で確認し、不能は阻害要因として記録する。
  3. tmp_path候補だけを除去する模擬切り戻しを行い、有効設定・registry・DBのハッシュ不変を確認する。将来適用する場合も承認済み差分と旧ハッシュを保存して該当差分だけ戻す。
- **確認**: 無通信・無DB・無自動上書き、6件dry-run、誤統合なし、robots拒否、待機、抽出正解fixtureが全て満たされる。検証失敗でも有効設定は元のまま。
- **完了条件**: 12ステップの検証結果と未承認候補が区別される。資料承認や依存契約が未完なら収集対象を増やさない。
- **工数目安**: 3時間（受入1、静的確認1、切り戻し1）。

## 検証記録・最終完了判定

2026-09-17は計画書とソースの静的確認のみ。実収集・DB操作・テスト実行は行っていない。今回再実行したCIコマンドもflake8が `EntryPoints.get` のAttributeError、mypyが未導入であり、合格を主張しない。依存の自動インストールもしない。今回の切り戻し対象は本計画書の差分のみ。他の既存実装・候補ファイル・運用データに触れない。
