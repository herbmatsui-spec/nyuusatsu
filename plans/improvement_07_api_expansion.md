# 改善案07: 既存APIへ共通検索・認証・権限契約を接続する計画

## 旧計画の評価（2026-09-17、実装を読み直した結果）

判定: ルートやスキーマは大部分が存在する。エンドポイントを増やすより先に、既存ルートの認証、地域範囲、検索仕様、保存検索サービスへの配線を完成させる。HTTP境界の担当に限定し、他計画が所有する検索・通知・課金ロジックを複製しない。

| 旧計画の問題 | 現在の証拠 | 修正方針 |
| --- | --- | --- |
| schemas.pyと入札詳細/一覧を新規作成する | `search_api/schemas.py:19-70` と `search_api/main.py:198-251` に存在 | 既存型/ルートを改修し、HTTP互換性を明示する |
| 複数地域対応とするが実装差を確認しない | `search_api/main.py:232` はprefectureの先頭要素だけをrepositoryへ渡す | 01の正規条件と04のscopeを渡し、先頭だけを採用しない |
| 検索APIの認証は保存検索だけでよいとする | `search_api/main.py:198-265`、`search_api/award_api.py:26-55`、`search_api/forecast_api.py:21-56` に利用者/権限依存がない | 入札・落札・発注見通し・関連予測・旧検索にも認証とscopeを適用 |
| 認証実装が安全に利用可能だと仮定する | `services/auth_service.py:57-72` は固定JWT秘密、sub変換の例外、無効利用者の確認漏れがある | 公開前の必須是正として既存AuthServiceを修正し、別認証基盤は導入しない |
| 保存検索CRUDもAPI側で作る | `search_api/user_api.py:49-120` に所有者確認付きCRUDあり。59-73行と138-153行は日時未指定でrepositoryへ直接作成 | 所有者検査を保持し、02のサービスへHTTPから委譲。日時/条件検証を07へ複製しない |
| forecastsを勝率/予測金額APIとする | 実URLは `search_api/forecast_api.py:10` の `/api/forecasts`。`database/models/_generated.py:447-469` は発注見通し | 発注見通しと価格分析を別概念として公開。勝率学習モデルを作らない |
| 既存レスポンス形の違いを無視する | `search_api/schemas.py:26-32` はitems/page/size、`search_api/forecast_schemas.py:31-35` はitems/page/per_page、共通検索は `services/search_service.py:124-141` のresults/total/offset/limit | 内部正規契約を変えず、HTTPの既存形式は薄いadapterで保持 |
| 運用指標と例外が無条件で公開される | `search_api/metrics_api.py:9-58` は依存なしでサービスを生成。`search_api/main.py:291,306` と `search_api/forecast_api.py:49` は例外文字列をHTTPへ返す | 運用権限を明示し、外部例外詳細を漏らさない |
| API上限をUIだけで扱えるとする | `services/api_usage.py:11-51` はUIのcurrent userを参照し、checkとincrementが別。既存 `database/models/api_usage.py:8-18` に月単位一意制約あり | 新台帳を作らず、既存上限処理の安全な認証済み引数契約が完成するまで公開停止。07は呼出配線のみ |
| TestClientがあれば安全な試験とする | `tests/test_search_api.py:16-19` は依存上書きなし、359-368行は実normalizer/healthを呼び500も許容。`tests/conftest.py:12-21` は永続DBを設定 | 全依存を隔離してから試験。正常系に500を許容しない |

## 範囲・非目標・対象パス

- 今回は本計画書だけを改訂する。以下の実装・試験には別途許可が必要。コード・追加文書・実DBを変更せず、インストール・サービス起動・LLM・Stripe・メールを実行しない。
- 担当範囲: 既存AuthServiceのAPI公開前是正、既存FastAPIの依存注入、入力/出力adapter、ステータス・エラー・OpenAPI、隔離したHTTP契約試験。保存検索/通知のCRUDと配送は02、検索は01/03/06、権限解決は04の所有で、07はHTTP配線のみ。
- 非目標: 新しいマイクロサービス、APIキー管理基盤、OAuth導入、Dockerfileやcomposeの再作成、外部ガイド追加、予測モデル学習、品質集計の再実装、LLMによる資格正規化の実行、独立quota台帳。既存ルートの安全な互換接続を優先する。
- 【既存・修正候補】`search_api/main.py`、`search_api/schemas.py`、`search_api/user_api.py`、`search_api/award_api.py`、`search_api/forecast_api.py`、`search_api/forecast_schemas.py`、`search_api/quality_api.py`、`search_api/metrics_api.py`、`services/auth_service.py`、`config.py`、`tests/test_search_api.py`、`tests/unit/test_auth_service.py`。
- 【既存・他計画所有/参照】`utils/plan_gate.py`（04）、`services/search_service.py`（01/06）、`services/award_search_service.py`（03）、`services/saved_search_service.py` と `services/notification_service.py`（02）、既存発注見通し/品質/利用量サービス。
- 【新規提案・07では作らない】01が `services/search_criteria.py` に置くSearchCriteria v1と互換adapter。04が既存 `utils/plan_gate.py` 内に追加するAccessScope。HTTP共通依存は既存 `search_api/user_api.py` を再利用し、必要関数を追加する。新しいAPIサービスファイルや文書は作らない。

## 依存順序とAPI契約

### 実行順序・所有者

「隔離基盤 → 04権限契約 → 01 → 03/06 → 02 → 05 → 07 → 09」を基準とし、08は独立。04の実料金/決済承認は別の運用停止条件。01は04の注入可能scopeで先行試験できるが、04/07の実認証まで一般公開は禁止する。07のHTTP完成を01/02/04のサービス完成条件にせず、循環依存を作らない。09の分析表示は後段であり、07では未検証スコアを確率として公開しない。

### 共通検索入力と返却

- 01所有の `SearchCriteria v1`: `keyword`、`exclude_keywords`（包含と別のNOT）、`use_or`、`prefecture`（2桁文字列の配列）、`organization`、`bid_type`、`announcement_from/to`。
- 06の任意拡張: `budget_min/max`、`qualification_keywords`、`deadline_from/to`、`deliverables_keyword`、許可リスト方式の `sort_column/direction`。金額は円、税区分はソースで確認できなければ不明。公告日を納期に置き換えない。
- サービスの正規返却は `results,total,offset,limit` のまま。既存 `/bids` は当面 `items,total,page,size,total_pages` を維持し、HTTP adapterだけで変換する。page/sizeからoffset/limitへ変換し、サービスのキーをitemsへ改名しない。旧 `/search` の配列も当面維持するが認証・権限の免除にはしない。
- HTTP入力では既存qをkeyword、published_after/beforeをannouncement_from/toへ一度だけ変換する。正規名との両指定で内容が異なる場合は422とし、どちらかを黙って優先しない。複数prefectureは全件検証し、先頭だけ採用しない。
- Pydantic入力検証では負のoffset相当、size=0/101、逆転日付/金額、無効地域、未許可sortを422。既存上限size=100を保持。本文からuser_id、plan、許可地域、内部日時を採用しない。
- 保存先は既存 `SavedSearch.criteria_json`。旧 `use_not` や `mobile_ui` は01の互換adapterを通じて02が扱う。07はcriteria_jsonという既存HTTP表現を維持し、JSONの意味検証・非アクティブ維持・日時設定を02へ委譲する。

### 認証・地域・機能・エラー

- HTTP依存はトークンから既存AuthServiceで有効DB利用者を得て、04の `resolve_access_scope(user, now)` を呼ぶ。AccessScopeはuser_id、allowed_prefectures、features、announcement_fromを持つ。HTTPリクエストの所有者IDやプラン値は使わない。
- 要求地域と許可集合の積集合、公告下限を検索前に適用。未指定地域は許可集合、空集合は0件。詳細・落札の関連入札・見通しの機関・予測元入札の地域も同じscopeで確認し、範囲を証明できないレコードは提供しない。集計totalを絞り込み前に計算しない。
- 認証なし/無効/期限切れ/無効利用者は401とBearer challenge、認証済みの機能不足は403、存在なし/他人/地域外詳細は同じ404、入力不正は422、使用上限超過は429、予期しない障害は情報を伏せた500。停止中の機能は提供せず、承認済みのエラー仕様をOpenAPIにも反映する。
- 運用metrics/qualityは04の機能と既存ロール権限で制限する。データ検索API権限だけで運用情報を返さない。診断のDB/Redis/LLM接続をTestClientから実行しない。
- 既存 `services/api_usage.py` を認証済み利用者・sessionで呼べる、原子的な上限予約契約へ整える作業はサービス所有側の前提。07で別カウンタを作らない。月単位一意制約を保持し、残り1回の同時要求は最大1件だけ許可する。未完成なら本番APIを閉じ、試験はstubを注入する。
- `/api/forecasts` は発注機関が公表した見通し。`/price_predictions/{bid_id}` は別の既存分析値で、09の意味・confidence/score_kind契約が確定するまで校正済み勝率として扱わず、未検証予測の公開は停止する。03所有の落札金額・落札率の意味も再定義しない。

## 実装ステップ

### ステップ 1: 全API依存を一時DBとモックへ差し替える
- **対象**: 【既存】`tests/test_search_api.py`、`tests/unit/test_auth_service.py`、参照 `tests/conftest.py`。
- **作業**:
  1. import時に永続DBへ向かわないよう先に試験用設定を注入し、tmp_path/in-memoryのsessionを作る。TestClientの別スレッドでも同じ隔離DBになる接続設定を確認する。
  2. main/user/award/qualityのDB依存、forecastサービス、旧検索、normalizer、metrics/health、quotaを全て上書きする。直接生成されるサービスは試験開始前にモック化する。
  3. HTTP/SMTP/Stripe/LLMを拒否する既定モックと、fixture終了時のdependency_overrides復元を追加する。正常試験の「200または500」を200の固定期待にする。
- **確認**: A/Bと地域13/27のfixtureを作っても永続DB接続・外部通信0。`/qualification/normalize` は固定モック結果だけ、`/metrics/health` は診断を起動せず固定結果だけを返す。
- **完了条件**: `tests/conftest.py:12-21` の永続DB副作用を避けたことが確認され、隔離前のpytest実行を必要としない。
- **工数目安**: 4時間（DB1時間、依存差替1.5時間、遮断/復元試験1.5時間）。

### ステップ 2: 既存JWT検証の公開前不備を是正する
- **対象**: 【既存】`services/auth_service.py`、`config.py`、`tests/unit/test_auth_service.py`。
- **作業**:
  1. 固定秘密への依存を廃止して既存設定経由の必須秘密を使い、未設定ではトークン発行/検証を停止する。秘密自体をコード、試験ログ、レスポンスに置かない。
  2. 許可アルゴリズムとexp/sub必須を明示し、不正subの型/変換例外を認証失敗として扱う。発行側と検証側の時刻契約をそろえる。
  3. subからUserをDBで再取得し、存在とis_activeを確認する。秘密変更後の旧固定秘密トークンを受け入れる互換fallbackは作らない。
- **確認**: 一時試験用秘密で発行した正常トークンだけ有効。期限切れ、欠落sub、非数値sub、無効利用者は全て認証失敗となり500にならない。設定未指定は発行不可。具体的な攻撃手順は作らない。
- **完了条件**: API公開に必要なJWT境界が試験済みで、利用者再ログインが必要な変更を公開ゲートに明記している。
- **工数目安**: 4時間（設定1時間、検証1時間、境界試験2時間）。

### ステップ 3: 共通HTTP認証・scope依存を用意する
- **対象**: 【既存】`search_api/user_api.py`、`tests/test_search_api.py`。04の `utils/plan_gate.py` を利用。
- **作業**:
  1. 既存Bearer依存の欠落時挙動を401に統一し、認証済みUserと同じrequestのDB sessionを共通依存から渡す。
  2. 04のscope解決を呼ぶHTTP依存を既存ファイルに追加し、ドメイン拒否を401/403へ変換する。課金ロジックをここへ書かない。
  3. 機能別依存と既存quota契約のstub注入点を定義し、API側で生のplan文字列を比較しない。
- **確認**: Bearerなし/無効トークンは401とWWW-Authenticate、正常利用者でもfeatureなしは403。リクエストに偽のuser_id/planがあってもscopeはDBのA由来で変わらない。
- **完了条件**: 他ルーターが同じ依存を再利用でき、循環importや複数の独自認証実装がない。
- **工数目安**: 3時間（依存1時間、エラー変換1時間、試験1時間）。

### ステップ 4: HTTP条件adapterと既存ページ形式を固定する
- **対象**: 【既存】`search_api/main.py`、`search_api/schemas.py`、`tests/test_search_api.py`。01の条件型を利用。
- **作業**:
  1. q/keyword、published_after/beforeとannouncement_from/toの対応を一つのadapterにまとめ、重複指定の矛盾を拒否する。
  2. 01/06の全条件を型付きで受け、地域・日付・金額・sortの意味検証は共有契約へ委譲する。
  3. page/sizeからoffset/limit、正規resultsから既存itemsへの変換を明示し、既存スキーマを破壊しない。
- **確認**: page=2,size=20はoffset=20,limit=20。q=道路とkeyword=橋の併記は422。prefecture=13,27は2件とも渡る。total=0のtotal_pagesは0、正規サービス返却キーは変わらない。
- **完了条件**: API独自SearchCriteriaを作らず、入力互換と出力互換が独立したテストになる。
- **工数目安**: 4時間（入力adapter1.5時間、出力1時間、試験1.5時間）。

### ステップ 5: 入札一覧を共通検索とscopeへ接続する
- **対象**: 【既存】`search_api/main.py`、`tests/test_search_api.py`。01/06の検索サービスを利用。
- **作業**:
  1. `/bids` の認証/API権限依存を追加し、repositoryへの独自条件渡しを共通検索呼び出しへ置換する。
  2. 条件とscopeを同時に渡し、レスポンスだけ既存items/page形式へadapter変換する。詳細が必要な再読込も同scopeの許可IDだけに限定する。
  3. total・順序・NULL・複数地域・除外条件の期待値を01/06のfixtureと一致させる。
- **確認**: 地域13許可のAが13と27を要求してもitems/totalに13しか含まれない。包含「道路」、除外「清掃」で除外案件は0。予算0とNoneを混同せず、不正sortは422。ページ間で同じIDが重複しない。
- **完了条件**: `/bids` で独自NOTや先頭地域だけの処理がなく、一覧とtotalが同じscopeで計算される。
- **工数目安**: 4時間（配線1時間、返却整合1時間、契約試験2時間）。

### ステップ 6: 入札詳細と旧検索の認可をそろえる
- **対象**: 【既存】`search_api/main.py`、`search_api/schemas.py`、`tests/test_search_api.py`。
- **作業**:
  1. `/bids/{bid_id}` に認証/機能/scopeを適用し、地域外・日数外・不明地域は不存在と同じ404にする。
  2. BidDetailの公開項目を点検し、内部運用メモや非公開分析項目を無条件で出さない。既存利用者向け互換変更はOpenAPIの説明に明記する。
  3. 旧 `/search` も同じ認証・権限を適用し、旧引数を対応可能な共通条件へ変換する。旧配列は保持し、変換不能条件は明示エラーにする。
- **確認**: 許可案件は200、同じ地域外案件と存在しないIDは同じ404形式。旧 `/search` も匿名では401、Aで地域外データ0。結果本文に秘密、所有者の内部メモを含めない。
- **完了条件**: 旧ルートを経由した認可漏れがなく、内部サービスに新しい検索ロジックを複製しない。
- **工数目安**: 4時間（詳細1時間、旧adapter1.5時間、回帰1.5時間）。

### ステップ 7: 落札APIを03の意味と地域scopeへ接続する
- **対象**: 【既存】`search_api/award_api.py`、`search_api/schemas.py`、`tests/test_search_api.py`。03のサービス契約を利用。
- **作業**:
  1. 落札一覧/詳細に共通依存を追加し、03のscope対応済み取得を呼ぶ。07で地域推測の文字列一致を実装しない。
  2. budget_amountとcontract_amount、落札日と公告日、落札率の単位を03の契約に合わせて説明/入力名を点検する。
  3. 関連入札の地域を立証できない行の扱いを03の保守的契約に従わせ、totalと詳細の両方で試験する。
- **確認**: 予算1000万円/契約800万円のfixtureでbudgetとcontractを取り違えない。地域外/関連不明詳細は404、一覧totalにも含まれない。認証不足401、機能不足403を保持する。
- **完了条件**: 03の統計/金額解釈をAPI側で再計算せず、既存 `/awards` URLとページ形式を保持する。
- **工数目安**: 4時間（配線1時間、意味照合1時間、試験2時間）。

### ステップ 8: 発注見通しと既存価格分析を区別して制限する
- **対象**: 【既存】`search_api/forecast_api.py`、`search_api/forecast_schemas.py`、`search_api/main.py`、`search_api/schemas.py`、`tests/test_search_api.py`。
- **作業**:
  1. 実URL `/api/forecasts` とitems/page/per_pageを維持し、機関の確認済み地域を使える既存サービス契約へscopeを渡す。未対応なら公開を停止し、全件取得後の見かけの絞り込みで代用しない。
  2. 発注見通しの説明と実レスポンス型をそろえ、未使用ForecastItemと既存ForecastResponseを勝率型として統合しない。
  3. `/price_predictions/{bid_id}` は元入札のscopeとprediction権限を確認する。09のscore_kind/confidence等の意味が未確定な値は公開停止とし、勝率として加工しない。
- **確認**: forecast fixtureの予定公告日・予定予算・公表元をそのまま返し、勝率フィールドを追加しない。地域外機関の見通しは一覧0/詳細404。予測権限なしは403、地域外予測元は404、LLM呼出0。
- **完了条件**: 調達予定とヒューリスティック分析が混同されず、09待ちでも見通し部分を独立して試験できる。
- **工数目安**: 6時間（小作業1: 見通し配線/試験2時間、小作業2: 型/ページ互換試験2時間、小作業3: 予測停止/認可試験2時間）。

### ステップ 9: /meを02のCRUDサービスへ委譲する
- **対象**: 【既存】`search_api/user_api.py`、`search_api/schemas.py`、`tests/test_search_api.py`。
- **作業**:
  1. 保存検索/alertsの直接repository作成・更新を02のサービスへ置換し、認証済みUser/scopeを渡す。既存のGET/POST/PUT/DELETE URLを保持する。
  2. 未指定更新項目と明示nullを区別し、変更不可列と余分なuser_id/plan入力を422にする。サービスの所有権エラーを一様な404に写す。
  3. 通知先種類を02のemail/slack/teams契約に合わせ、検索停止/通知先停止を既存is_active更新で表現する。スキーマの単なるwebhook表記との不一致を解消する。
- **確認**: Aの検索をBがGET/PUT/DELETEしても404でDB不変。正常POSTは201でdatetimeが再読込可能、DELETEは204で本文なし。mobile_ui旧条件の非アクティブ検索がGETだけで有効化されない。S1停止でS2は不変。
- **完了条件**: CRUD・条件変換・日時・outbox・停止ロジックを07に複製せず、02が単体で検証した振る舞いをHTTPへ写すだけになる。
- **工数目安**: 4時間（保存検索配線1時間、alerts配線1時間、所有権/停止試験2時間）。

### ステップ 10: 運用ルートとエラー返却を最小情報に制限する
- **対象**: 【既存】`search_api/main.py`、`search_api/metrics_api.py`、`search_api/quality_api.py`、`search_api/forecast_api.py`、`tests/test_search_api.py`。
- **作業**:
  1. metrics/qualityに04の運用権限依存を適用し、normalizerも許可なしでは呼べないようにする。既存LLM機能の拡張・実行は行わない。
  2. 直接生成される診断/集計サービスを依存として注入できるようにし、HTTP配線の外部副作用を試験で遮断する。
  3. `detail=str(e)` を安全なメッセージへ変更し、既存error.code/message構造と401 challengeを維持する。サーバー内部のPydantic不整合を利用者入力422へ誤分類しない。
  4. 422のdetailsから機密入力を除き、予期しないエラーでも秘密・接続文字列・内部パスを返さない。ログにも生トークン/宛先/リクエスト全文を出さない。
- **確認**: 一般API利用者のmetricsは403、運用権限fixtureだけ200。モック例外にダミー機密文字列を含めてもHTTP本文に出ない。無効パラメータは422、サービス故障は固定500、正常normalizer試験で500を許容しない。
- **完了条件**: 運用情報と一般データの境界が明示され、HTTP試験で実診断/LLMが起動しない。
- **工数目安**: 6時間（小作業1: 運用依存/試験2時間、小作業2: 依存差替/試験2時間、小作業3: エラー形式/機密試験2時間）。

### ステップ 11: 公開契約と利用上限のHTTP配線を照合する
- **対象**: 【既存】`search_api/main.py`、`search_api/user_api.py`、`search_api/schemas.py`、各既存router、`tests/test_search_api.py`。
- **作業**:
  1. 承認済みの既存quota予約サービス契約だけをHTTP依存から呼び、上限超過を429へ写す。原子的契約が未完成ならstub試験だけに留め、公開停止とする。
  2. 既存FastAPIのsummary/description/responses/deprecated設定で認証、地域制限、別名、ページ形式、税不明、発注見通し、停止機能を説明する。新しいMarkdownやコードコメントを追加しない。
  3. `app.openapi()` を隔離環境で検証し、ルート・必須Bearer・応答型・エラー一覧が実装と一致するか確認する。
- **確認**: 残り1回のquota契約モックは最初の要求だけ許可し次は429、他人の利用量に加算しない。OpenAPIは実URL `/api/forecasts` を持ち、存在しない `/forecasts` を稼働済みと表示しない。pageとoffsetのサービス契約を混同しない。
- **完了条件**: 利用上限の実装を07で新造せず、配線済み/未完成を区別して公開判断できる。OpenAPI閲覧に実サーバー起動が不要。
- **工数目安**: 4時間（quota配線1時間、OpenAPI1.5時間、照合試験1.5時間）。

### ステップ 12: 既存ルート全体の認可と互換性を回帰判定する
- **対象**: 【既存】`tests/test_search_api.py`、`tests/unit/test_auth_service.py`、本計画の完了ゲート。
- **作業**:
  1. 匿名、A、B、機能不足、運用権限あり、失効契約のfixtureを全ルートの認可表へ適用する。
  2. 正常/404/422/429/500、ページ末尾、複数地域、旧入力、保存検索部分停止、forecast意味の契約試験を照合する。
  3. HTTP追加前後の既存ルート/出力キーを比較し、認証強化による意図した変更と未解決のサービス前提を明示して公開可否を判定する。
- **確認**: `/bids`、`/bids/{id}`、`/awards`、`/api/forecasts`、`/price_predictions/{id}`、`/search`、`/me`、metrics/quality/normalizeのいずれにも認可漏れがない。外部通信・永続DB接続は全試験で0。
- **完了条件**: 01/02/03/04/06のサービス責任を維持したままHTTP契約の合否を示せる。未検証予測と未完成quotaがある場合は対応機能を公開しない。
- **工数目安**: 4時間（認可表1時間、互換/境界試験2時間、ゲート判定1時間）。

## 関連テストと実行前提

- 本文改訂時点ではテスト・サービス・インストールを実行しない。`tests/test_search_api.py` は現在shared DB依存で、直ちに `--noconftest` を付けて実行できるとはみなさない。
- ステップ1で自己完結fixture、全DB依存上書き、ネットワーク遮断を検証した後のみ、候補は `pytest --noconftest tests/test_search_api.py tests/unit/test_auth_service.py -q`。自己完結を満たさなければ基盤担当の隔離完了後に通常の明示対象コマンドへ変更し、永続DBへ接続しないことを先に確認する。
- HTTP試験は正常データを合成し、未認可データを実環境から取得しない。トークン検証は一時秘密・無効fixtureのみを使い、攻撃の実演や侵入試験を行わない。
- `.github/workflows/test.yml:18-20` のコマンドは `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics` と `mypy .`。共有基準結果（2026-09-17）はflake8が `AttributeError: EntryPoints.get`、mypyはcommand not found。静的解析基準は取得不能であり、コードが通ったとは書かない。環境修復・再実行は別承認後。
- リスクに対応する最低試験: 他人の保存検索不変、無効利用者拒否、地域外詳細の非開示、totalのscope一致、legacyルート保護、UTC境界、未知sort拒否、quotaの429配線、未検証予測停止、機密のない500、全依存の復元。

## ロールバック

1. 先に公開APIの対象機能を停止し、認証/地域依存を外して旧版へ戻さない。旧無認証ルートを互換性のために再公開しない。
2. HTTPadapterの変更だけを戻す場合も04のscopeと07の認証是正は保持する。保存検索・配送outboxは02の所有であり、07のrollbackで削除/再生成しない。
3. 秘密切替前の固定JWT秘密を復活させない。必要な既存利用者の再ログインは公開前に扱いを決め、無期限互換トークンを作らない。
4. quotaや依存サービスの契約が未完成ならその機能は閉じたままにする。DB migrationや実Stripe同期をHTTProllbackに含めず、各所有計画の別承認手順へ戻す。

## 完了ゲート（公開・デプロイを自動実行しない）

- 12ステップの具体入力と期待結果がそろい、既存URL/HTTP形式の互換性と認証追加による意図した変更が区別されている。
- 04のDB由来scopeを全取得経路へ適用し、01/06の条件と正規返却、03の落札意味、02の所有権/日時/停止をHTTPから再実装せず利用している。
- quota原子性、JWT秘密設定、無効利用者、運用権限、地域不明データ、未検証予測の扱いが未解決なら公開不可。09のスコアを校正済み勝率と称しない。
- 静的解析基準未取得は未解消事項として残す。モック試験やOpenAPI確認の完了は、uvicorn/コンテナ起動、実LLM・メール・Stripe、実DB更新、本番デプロイの許可ではない。
