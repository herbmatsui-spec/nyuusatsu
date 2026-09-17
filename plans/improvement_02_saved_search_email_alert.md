# 改善案02: 保存検索とメールアラートの既存実装を安全に接続する計画

## 旧計画の評価（2026-09-17、実コードを読み直した結果）

判定: 全面新規開発ではなく、既存CRUD・条件形式・配信の整合性を直す計画に置き換える。以下はソースから確認できた事実であり、動作試験済みという意味ではない。

| 旧計画の問題 | 現在の根拠 | この計画での扱い |
| --- | --- | --- |
| SavedSearchとリポジトリを新規作成する | `database/models/saved_search.py:1-4` は再公開。実体は `database/models/_generated.py:490-499`、リポジトリは `database/repositories/__init__.py:191-213` | 既存の `criteria_json`、整数の所有者ID、通知日時を保持し、同名モデル・並行テーブルを作らない |
| 保存フォームとAPIを一から追加する | `app_dashboard.py:552-599` にフォームがあり、572行の `criteria=` は `services/saved_search_service.py:19` の引数と不一致。594行の辞書位置引数も `database/repositories/base.py:38-43` の `**kwargs` と不一致 | 本計画はサービスと既存通知UIを修正。既存 `/me` HTTP接続は07だけが担当 |
| 検索件数の増加だけで新着を判定する | `services/saved_search_service.py:38-52` は最大1000件を取得し、76-81行では未知条件を無視 | 01の共通条件処理を使い、案件IDと内容改訂を識別する。件数差は廃止 |
| 通知呼び出し完了を送達成功とみなす | `services/morning_digest_service.py:27-40` は送信後に日時を更新。`services/notification_service.py:59-82` は無効・設定不足・例外を成功と区別できない | 永続outboxと明示的結果を導入し、送信不能で成功日時を進めない |
| チャネル別配送の保証がない | `services/morning_digest_service.py:51-54` はチャネルURLを渡さず、`services/notification_service.py:29-57` は全体設定のURLを参照 | 個人ダイジェストから全体URLへのフォールバックを禁止 |
| 新しいschedulerを作る | 既存 `scheduler/scheduler.py:496-517` に毎朝ジョブがあるが、513行はgeneratorをcontext managerとして利用。`database/engine.py:23-34` 参照 | 既存ジョブだけを修正し、別常駐サービス・Redisキューを追加しない |
| 既存データ移行が考慮されない | `services/mobile_ui_service.py:41-57` は `mobile_ui` ラッパーで非アクティブ保存。`migrations/versions/202609131530_update_saved_search_user_id.py:19-35` はテーブルを削除して再作成 | 非アクティブを勝手に有効化せず、旧migrationの再適用で利用者データを失わない |
| 作成時刻と所有権の境界が曖昧 | `search_api/user_api.py:59-73,138-153` は日時未指定。モデルの `DateTime` のPython既定値は文字列（`database/models/_generated.py:498-499`） | 一時DBでflush・再読込を検証し、サービスからdatetimeを設定する。HTTP側で別実装しない |

## 範囲・非目標・対象パス

- 今回は本計画書の書き換えのみ。以下のステップは、別途実装を許可された後の手順である。コード・他の文書・実DBには変更を加えない。
- 実装範囲: 保存検索/通知先の所有者付きCRUD、旧条件の変換、既存検索の利用、配信outbox、停止・再試行、既存朝ジョブと通知設定画面。
- 非目標: 新しいアプリ・キュー基盤・メール事業者・HTMLテンプレート基盤・LLM呼び出し・実メール送信・Stripe操作・ユーザーガイド追加。検索仕様は01/06、課金権限は04、HTTPルートは07、モバイル接続は05の担当。
- 【既存・修正候補】`services/saved_search_service.py`、`services/morning_digest_service.py`、`services/notification_service.py`、`database/models/_generated.py`、`database/repositories/__init__.py`、`app_dashboard.py`、`scheduler/scheduler.py`、`tests/unit/test_saved_search_service.py`。
- 【既存・参照のみ/他計画担当】`services/search_service.py`（01/06）、`utils/plan_gate.py`（04）、`search_api/user_api.py` と `search_api/schemas.py`（07）、`services/mobile_ui_service.py`（05）。
- 【新規提案・未作成】既存 `migrations/versions/` 配下の配信台帳用追記migration（ファイル名・revisionは実装時に現行head確認後に決める）。台帳モデルとリポジトリは既存の実体ファイルへ最小追加する。新しい配送サービスは作らない。新しいテストが必要なら既存テストファイルへ追加する。

## 依存順序と共有契約

1. 全体順序は「隔離テスト基盤 → 04権限契約 → 01 → 03/06 → 02 → 05 → 07 → 09」。08は独立。04の実価格・決済承認はこの順序の前提ではなく、別の公開停止条件である。UI相互接続は後段に置き、01や04を02のUI完成待ちにしない。
2. 01所有の `SearchCriteria v1` は `keyword`、`exclude_keywords`（独立したNOT条件）、`use_or`、`prefecture`（2桁文字列の配列）、`organization`、`bid_type`、`announcement_from/to`。06の任意追加は `budget_min/max`、`qualification_keywords`、`deadline_from/to`、許可リスト方式の `sort_column/direction`。公告日と納期は別物。金額は円の抽出値で、税区分は確認できなければ不明。
3. 検索の正規返却値は `results,total,offset,limit` のまま。保存先は既存 `SavedSearch.criteria_json`。01所有の互換アダプターに旧 `keywords/min_budget/use_not` と `mobile_ui` を渡す。02では別の検索DSL・全文検索・LLM正規化を実装しない。旧 `use_not=true` は旧keywordを除外側へ移すなど、01で確定した意味を保持し、不明条件を黙って捨てない。
4. 04所有の `utils/plan_gate.py` がDB上の有効ユーザーから共通 `AccessScope` を解決する。取得時も配信直前も要求地域と許可地域の積集合を適用し、空集合を全国扱いしない。失効・無効・未知権限は拒否。所有者ID・メール利用者IDをリクエストやUIの文字列から決定しない。
5. 02がサービス契約を所有する。既存 `SavedSearchService` に、認証済み利用者/検証済みscopeを受ける一覧・作成・取得・更新・削除・有効化を集約する。通知先CRUDは既存 `NotificationService` に集約する。07は入力変換とHTTP結果変換だけを行う。
6. 配信契約: DB内の案件重複登録を防ぐ台帳/outboxを同一テーブルで扱う。識別子は `(user_id, channel_id, saved_search_id, bid_id, revision)` に一意制約を付ける。`revision` は正規化した通知対象項目の決定的ハッシュとし、送信時刻・取得件数を含めない。名前・URL等の個人データをログへ出さない。
7. 配信対象を有界の時刻窓と安定した案件カーソルで列挙し、outbox追加と走査チェックポイントを同じDBトランザクションでcommitする。`last_notified_at` は成功通知の観測値として保持し、走査カーソルとして使わない。最初の有効化は現在時刻を起点にし、1970年から全件配信しない。
8. 外部SMTPの厳密なexactly-onceは保証不可能。DB内は重複登録防止、外部配送は再試行で重複する可能性がある。受理済みか不明なtimeoutは `unknown` として自動再送を止める。停止は認証済みの「この保存検索」または「この通知先」に限定し、全ユーザー停止や無署名の一括解除URLを設けない。

## 実装ステップ

### ステップ 1: 保存検索試験を実DBから隔離する
- **対象**: 【既存】`tests/unit/test_saved_search_service.py`、基盤担当の `tests/conftest.py` を参照。
- **作業**:
  1. 既存のin-memory fixtureを確認し、DBを開くimportやセッション生成の前に試験用設定を注入する。
  2. SMTP、HTTP、Stripe、LLM、scheduler起動を失敗するモックへ置換し、必要な呼び出しだけ個別に期待値を設定する。
  3. 利用者A/B、地域13/27、明示datetimeを持つ案件を作る独立fixtureを追加する。
- **確認**: A/Bの合計2件が一時DBにだけ入り、fixture終了後は破棄される。接続先に `tests/fixtures/test.db` や `bids_system.db` が一度も現れず、外部通信回数0。
- **完了条件**: `tests/conftest.py:12-21` の永続DB副作用を避ける手段が確認されてからのみ後述の試験を実行できる。`--noconftest` は全fixtureが自己完結する場合に限る。
- **工数目安**: 3時間（fixture 1時間、遮断1時間、確認1時間）。

### ステップ 2: 保存条件を正規形式へ変換する
- **対象**: 【既存】`services/saved_search_service.py`、`tests/unit/test_saved_search_service.py`。01の条件アダプターを利用。
- **作業**:
  1. JSON構文とオブジェクト型を検証し、01の互換アダプターへ渡す入口を一つにする。
  2. `keywords/min_budget/use_not/mobile_ui` の変換結果を正規化して `criteria_json` に保存する。変換できない条件は原文を残し有効化を拒否する。
  3. 既存非アクティブ検索を読み込んでも有効化・一括更新しない試験を追加する。
- **確認**: `{"keywords":"道路","use_not":true}` は除外条件になり、包含条件にはならない。`{"mobile_ui":{"keyword":"道路","prefectures":["13"]}}` は変換可能項目を保持する。JSON配列・壊れたJSON・未対応キーは明示エラー、全件検索にはならない。
- **完了条件**: 同じ正規条件の再保存で意味が変わらず、旧原文の破壊的な一括migrationがない。
- **工数目安**: 4時間（入力検証1時間、変換接続1.5時間、試験1.5時間）。

### ステップ 3: 所有権付き保存検索CRUDをサービスへ集約する
- **対象**: 【既存】`services/saved_search_service.py`、`database/repositories/__init__.py`、`tests/unit/test_saved_search_service.py`。
- **作業**:
  1. 作成以外の取得・一覧・更新・削除を既存SavedSearchに対して追加し、毎回DBの利用者IDで絞る。検索名は空白除去後1〜100文字とする。
  2. 作成/更新日時をdatetimeで明示設定し、更新可能列を名前・条件・有効状態に限定する。任意の `user_id` や通知時刻は受け付けない。
  3. 認証・04の保存権限・地域scopeを確認してから変更し、存在しないIDと他人のIDを同じドメインエラーにする。
- **確認**: Aが作成した検索をBが取得・更新・削除できず、件数と所有者は不変。正常作成をcommitして別セッションで再取得すると日時はdatetime、JSONは正規形。所有者偽装入力は拒否される。
- **完了条件**: HTTPやUIなしでCRUD契約を検証でき、既存SavedSearchの再作成が不要。
- **工数目安**: 4時間（CRUD1.5時間、権限/日時1時間、試験1.5時間）。

### ステップ 4: 通知先と停止範囲をサービスで固定する
- **対象**: 【既存】`services/notification_service.py`、`database/repositories/__init__.py`、`tests/unit/test_saved_search_service.py`。
- **作業**:
  1. 既存NotificationChannelの一覧・作成・更新・無効化に所有者確認とdatetime設定を加え、種類をemail/slack/teamsに限定する。
  2. メール先の利用確認が取れない場合は非アクティブとし、改行入り宛先・空宛先を拒否する。Webhookは承認済みHTTPS宛先以外を有効化せず、個人通知の全体設定代用を禁止する。
  3. 「検索だけ停止」と「通知先だけ停止」を別操作とし、停止対象の未送信outboxをcancel対象にするサービス契約を追加する。
- **確認**: Aの検索S1停止はS2やBに影響しない。Aのemailチャネル停止は同じAの別チャネルを消さない。宛先未確認・未承認Webhookでは送信モック呼び出し0。
- **完了条件**: 07と通知UIが共有できる通知先CRUD・部分停止契約があり、宛先IDは他人へ付け替えられない。
- **工数目安**: 4時間（検証1時間、所有権/停止1.5時間、試験1.5時間）。

### ステップ 5: 既存通知設定画面をサービス契約へつなぐ
- **対象**: 【既存】`app_dashboard.py`、`tests/unit/test_saved_search_service.py`。
- **作業**:
  1. 通知設定部分だけで既存認証から利用者を取得し、`user_id="default"` の代替を削除する。
  2. `criteria=` と辞書位置引数の直接repository呼び出しをステップ3/4のサービス呼び出しへ置換する。
  3. 非アクティブも一覧表示し、保存検索ごとの再編集・明示有効化・停止を接続する。01/05側のUIはここで編集しない。
- **確認**: 認証なしでは書込0。認証済みAが「道路、地域13」を保存するとAの正規JSON1件ができ、条件/通知先保存でTypeErrorがない。無効な入力で成功表示せず、再表示後も停止状態を保持する。
- **完了条件**: 通知画面に独自検索条件処理や独自所有者決定がなく、他画面の利用者実装を保持する。
- **工数目安**: 3時間（呼出修正1時間、状態表示1時間、UIモック確認1時間）。

### ステップ 6: 新着候補の列挙を共通検索へ置き換える
- **対象**: 【既存】`services/saved_search_service.py`、`tests/unit/test_saved_search_service.py`。01/06の共通検索処理を利用。
- **作業**:
  1. `_matches` の別解釈と `list_all(limit=1000)` を使わず、共通条件と04のscopeを同じqueryに適用する。
  2. 1回の走査上限時刻を固定し、更新日時とIDの安定カーソルで小さなbatchに分ける。NULL更新日時の扱いと改訂抽出はfixtureで明示する。
  3. 通知項目から決定的revisionを作り、同件数でも案件が入れ替わった場合や既存案件の内容更新を候補化する。
- **確認**: 1001件目の対象を後続batchで取得し、再走査時の同一案件/同一revisionは同一キー。結果2件が別の2件に入れ替わっても新規キーが2個になる。地域27の非許可案件はtotalにも候補にも含まれない。
- **完了条件**: 件数差に依存せず、01と同じ条件の検索対象が一致する。検索中にLLM・crawlerを呼ばない。
- **工数目安**: 6時間（小作業1: 共通query接続/試験2時間、小作業2: 有界カーソル/試験2時間、小作業3: revision/境界試験2時間）。各小作業の確認後に次へ進む。

### ステップ 7: 最小配信outboxを既存DBへ追加する
- **対象**: 【既存】`database/models/_generated.py`、`database/repositories/__init__.py`、`tests/unit/test_saved_search_service.py`。【新規提案】配信台帳migration。
- **作業**:
  1. 同じテーブルに一意配信キー、固定payload、状態、試行回数、次回時刻、claim期限を定義する。検索側には走査窓・カーソルを最小追加し、既存通知日時を残す。
  2. 一意制約と検索/状態/再試行時刻のindexを追記migrationで追加する。既存のSavedSearch/NotificationChannelを作り直さない。
  3. 合成の既存データ入り一時DBでupgradeと互換読込を検証する。旧drop/create migrationを運用DBへ再実行しない。
- **確認**: 同じA/チャネル/S1/案件/revisionの二重登録は1行、別チャネルまたは別revisionは独立。migration後も既存検索ID・条件・所有者・非アクティブ状態が完全一致する。
- **完了条件**: 台帳を新しいRedis/workerなしで保持でき、追加列がなくても旧データの復元方法が定まる。
- **工数目安**: 4時間（モデル/制約1.5時間、migration1時間、データ保持試験1.5時間）。

### ステップ 8: outboxと走査カーソルを原子的に確定する
- **対象**: 【既存】`services/morning_digest_service.py`、`services/saved_search_service.py`、`database/repositories/__init__.py`、`tests/unit/test_saved_search_service.py`。
- **作業**:
  1. 初回有効化時刻を起点に窓を固定し、batch内の候補をステップ7のoutboxへ登録する。既定で過去全件通知をしない。
  2. 同じsessionの一つのtransaction内でoutbox追加とカーソル更新を行う。内部commitする `BaseRepository.create` をこの経路では使わずadd/flushに限定する。
  3. batch末尾のcommit失敗時は両方rollbackし、同じ窓の再実行で一意制約を利用して再開する。
- **確認**: outbox追加後/カーソル更新直前に故障を注入すると両方未確定。commit直後の再実行では台帳件数不変。無一致窓は送信成功とせず走査のみ進める。
- **完了条件**: 「カーソルだけ進み通知を失う」状態を生成せず、1検索の失敗で他の検索のsessionが壊れない。
- **工数目安**: 4時間（transaction1.5時間、再開1時間、故障注入試験1.5時間）。

### ステップ 9: 通知関数から配送結果を明示的に返す
- **対象**: 【既存】`services/notification_service.py`、`services/morning_digest_service.py`、`tests/unit/test_saved_search_service.py`。
- **作業**:
  1. 個人ダイジェスト向け呼び出しに明示した宛先を渡し、`sent/retryable/permanent/skipped/unknown` を区別する。既存の巡回通知呼び出しとの互換性を保つ。
  2. 設定不足・無効化・未対応チャネルを `sent` にしない。SMTP受理不明timeoutは `unknown`、受理拒否が確認できた一時エラーは `retryable` とする。
  3. プレーンテキスト本文に検索名・対象日・案件名・発注者・確認済み参照先・アプリ内停止方法を含め、件数上限と文字長を制限する。
- **確認**: メール成功/受理拒否/設定不足/timeoutのモックが異なる結果を返す。チャネルA/Bの送信先はそれぞれ明示値で、全体Slack設定は参照しない。秘密・メールアドレスをエラーログに出さない。
- **完了条件**: 外部送信なしで全結果を検証でき、呼び出しただけでは成功日時を更新しない。
- **工数目安**: 4時間（結果型1時間、宛先/本文1.5時間、試験1.5時間）。

### ステップ 10: 再試行と部分停止を台帳状態に反映する
- **対象**: 【既存】`services/morning_digest_service.py`、`database/repositories/__init__.py`、`tests/unit/test_saved_search_service.py`。
- **作業**:
  1. pendingまたは期日到来retryable行を条件付き更新でclaimし、同時実行の二重claimを拒否する。
  2. 配送直前に利用者・保存検索・チャネル有効性と最新地域権限を再確認する。対象外はcancelし、成功行だけをsentに更新する。
  3. 明示的な一時失敗だけ最大3試行に制限する。送信後DB更新前の停止、期限切れclaim、受理不明はunknownとして自動再送しない。
  4. 成功行は再実行で送らず、停止解除後も過去cancel行を自動再開しない。手動再送は当該所有者/検索/行だけを明示対象にする。
- **確認**: 2チャネル中1つ成功・1つ失敗なら再実行は失敗側だけ。claimの競合で送信1回。S1だけ停止した後の再試行ではS1送信0、S2は継続。権限縮小後に旧地域を再送しない。
- **完了条件**: 再試行上限・unknown・opt-out・replayの状態遷移が試験で固定され、SMTP exactly-onceを標榜しない。
- **工数目安**: 6時間（小作業1: claimと並行試験2時間、小作業2: retry/unknownと故障試験2時間、小作業3: scoped opt-out/replay試験2時間）。

### ステップ 11: 既存朝ジョブのsessionと実行境界を修正する
- **対象**: 【既存】`scheduler/scheduler.py`、`services/morning_digest_service.py`、`tests/unit/test_saved_search_service.py`。
- **作業**:
  1. digestラッパーだけを `database.engine.get_session()` のcontext managerへ変更し、generatorのAPI依存関数自体は変えない。
  2. 既存job IDを維持し、タイムゾーンをAsia/Tokyoの08:00として既存scheduler設定との整合を確認する。重複登録・並行実行を抑制する。
  3. ラッパーから有限batchのoutbox生成/配送を呼び、例外時rollbackとsession closeを保証する。停止設定では配送呼び出しを行わない。
- **確認**: schedulerモックへ登録される `morning_digest_job` は1件。ラッパー単体呼出でsessionが必ず閉じ、故障時rollback1回。日本時間08:00の次回時刻が期待する日付になり、他ジョブ登録は不変。
- **完了条件**: schedulerサービスを起動しなくてもcontext manager不整合と登録条件を検証できる。
- **工数目安**: 3時間（session修正1時間、ジョブ設定1時間、試験1時間）。

### ステップ 12: サービス契約を07へ渡す前に回帰判定する
- **対象**: 【既存】`tests/unit/test_saved_search_service.py`、本計画の完了ゲート。07は返却契約のみ参照。
- **作業**:
  1. CRUD→有効化→翌窓候補登録→擬似配送→停止→replayの一本の隔離シナリオを追加する。
  2. 旧条件・モバイル非アクティブ・1000件超・部分失敗・権限縮小・日時境界を個別試験と照合する。
  3. 07へ渡すサービス引数、返却値、所有権エラー、状態遷移が確定したか本計画のゲートで判定し、未確定項目は公開停止とする。
- **確認**: Aの許可案件のみが1回sentとなり、Bのデータ、停止済みS1、地域外、未確認宛先は送信0。同じ入力で再実行して台帳行数・sent回数が増えない。
- **完了条件**: 07のHTTP実装を待たずサービス単位で合否が決まり、実メール・本番schedulerを動かさず引継げる。
- **工数目安**: 3時間（シナリオ1時間、回帰1時間、ゲート照合1時間）。

## 関連テストと実行条件

- この計画改訂ではテスト、サービス、インストールを実行しない。`tests/conftest.py:12-21` が永続 `tests/fixtures/test.db` を強制するため、そのまま `pytest tests/` を実行しない。
- ステップ1の隔離とネットワーク遮断が確認できた後、自己完結fixtureが維持されている場合だけ `pytest --noconftest tests/unit/test_saved_search_service.py -q` を候補とする。自己完結を確認できない場合は基盤担当の隔離完了を待ち、フラグで問題を隠さない。
- 07のHTTP所有権試験は07で、05のモバイル接続試験は05で行う。02の完了をそのUI実装に依存させない。
- CI定義は `.github/workflows/test.yml:18-20` の `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics` と `mypy .`。2026-09-17の共有実行結果はflake8が `AttributeError: EntryPoints.get`、mypyはcommand not found。静的解析の基準結果は取得不能であり「コード合格」とは記録しない。環境修復の別承認後に再確認する。

## ロールバック

1. まず既存digestジョブの配送を停止し、pending/unknown/sent行とチェックポイントを保持する。停止前にoutboxを削除しない。
2. 旧配送実装へ単純に戻すと台帳を見ず再送し得るため、コードを戻す場合も配送停止を維持する。CRUDの旧形式読込互換だけを先に確認する。
3. スキーマは原則追加状態を保持して機能停止で戻す。破壊的downgradeや旧saved_searches再作成は行わない。一時DBで保持データの復元を検証してから、別承認の手順で対処する。
4. unknownの再送は対象を限定し、重複配送の可能性を確認して個別承認する。停止解除を一括replayとして扱わない。

## 完了ゲート（本番公開を自動実行しない）

- 12ステップの確認入力と期待結果が記録され、所有権・条件意味・地域積集合・原子的outbox・部分停止・replay・受理不明の試験がそろっている。
- 既存保存条件/非アクティブ状態が保持され、旧migrationのテーブル削除を本番へ再適用しないことを確認している。
- 04の実権限解決と07の認証接続が未完了なら公開不可。承認済み送信元/宛先・配信時刻・停止経路・再試行方針が未確定でも配送開始不可。
- 静的解析基準未取得は未解消事項として残す。計画完了・モック試験完了は、本番migration、実メール、scheduler有効化の許可を意味しない。
