# 改善案04: 地域権限の一元化と課金変更の安全性を確認する計画

## 旧計画の評価（2026-09-17、現行ソースを再確認）

判定: 地域プラン、選択地域列、決済UI、契約変更処理は既存であり、新規実装手順をそのまま実行しない。まずバックエンド権限契約を確定し、実料金・実決済は別承認まで停止する。

| 旧計画の記述 | 現在の根拠 | 修正方針 |
| --- | --- | --- |
| 地域プランとPrice ID設定を一から追加する | `config.py:154-191` に地域プラン、旧standard、価格、Price ID環境変数が存在 | 既存キーと旧契約を保持し、承認状態と権限を分離 |
| 既存Standardは24,800円とする | `config.py:174-181` のstandardは30,000、nationalは24,800。`app_billing.py:28,38` は税抜と表示 | コード内の数値も承認済み販売条件の証拠にはならない。旧案5,000/8,000/24,800円は未承認提案、税・競合現価も未検証 |
| Userへ選択地域列を新規追加する | `database/models/_generated.py:537-552` に列があり、`migrations/versions/add_allowed_prefectures_to_users_add_allowed_prefectures_to_users.py:21-28` にmigrationあり | 再追加・drop/createをしない |
| 選択数に空きがあれば任意地域を許可する | `utils/plan_gate.py:103-134` は未選択の地域でも枠が余ればTrue | 「選択できる」と「閲覧できる」を分離し、検索時は保存済み許可集合だけ使う |
| UI警告を主なアクセス制御とする | `utils/plan_gate.py:12-54` はStreamlitデコレーター、`search_api/main.py:198-265` はDB依存のみ | UIに依存しない共通scopeを04が所有し、01/02/03/05/06/07/09が利用 |
| プラン変更処理を一から作る | `services/billing_service.py:121-171` は次回更新時のSubscriptionScheduleを実装済み | 現行の予約方式・customer照合・1 item検査・失敗時releaseを保持し、モック回帰を足す |
| Webhookのプラン同期が不足する | `services/billing_service.py:190-205` にdispatch/commitがある。最新の `230-239` は旧プランを保持して地域縮小後にplanを更新 | 旧調査の「先にplan更新」不具合は読み直し時点で修正済み。利用者実装を保持し、回帰防止を計画する |
| Webhook受信だけで同期を信頼する | `app_webhook.py:13-27` は署名検証あり。一方 `services/billing_service.py:190-205` はevent IDの台帳・順序判定なし | 署名検証を残し、永続重複防止と契約単位の順序検証を追加 |
| 最終確認で実Stripeを操作する | `tests/billing/test_plan_gate_and_webhook.py:121-139` に地域縮小試験、`tests/billing/test_billing_ui.py:12-50` にUIモックがある | 実Price作成・実Checkout・本番migrationを完了条件にしない |

## 範囲・非目標・パスの区別

- 今回は本計画書のみ変更する。以下は別途実装許可後の手順。コード、他の文書、`.env`、実DB、Stripeを変更しない。
- 本計画が所有するもの: `utils/plan_gate.py` 内のバックエンド権限解決と共通scope型、地域選択検証、既存料金設定の承認停止、既存契約変更とWebhookの整合性。
- 非目標: 新しい認証方式/課金基盤/決済商品、価格の最終決定、競合サイト価格の断定、クローラーへの利用者別地域制限、全顧客一括移行、新しい説明文書。JWT修正とAPI配線は07。検索実装は01/03/06、配送は02、モバイルは05。
- 【既存・修正候補】`utils/plan_gate.py`、`services/billing_service.py`、`config.py`、`app_billing.py`、`app_webhook.py`、`database/models/_generated.py`、`database/repositories/__init__.py`、`tests/billing/test_plan_gate_and_webhook.py`、`tests/billing/test_billing_ui.py`。
- 【既存・参照/他計画担当】`services/auth_service.py` と `search_api/user_api.py`（07）、`services/search_service.py`（01/06）、既存User再公開モジュール、既存地域列migration。
- 【新規提案・未作成】Webhook処理済みイベントを最小保存する追記migrationを既存 `migrations/versions/` 配下へ追加する。名称とrevisionは実装時にheadを確認して決定。モデル/リポジトリは既存実体ファイルへ追加する。独立サービスや新しいキューは作らない。

## 依存関係と共有契約

### 実行順序

「隔離テスト基盤 → 04のステップ1〜4で権限契約確定 → 01 → 03/06 → 02 → 05 → 07 → 09」を基準とする。08は独立。04後半の価格承認・決済検証待ちは01の隔離実装を止めない。01は注入可能なfail-closed scopeを先に試験できるが、04の実権限解決と07の認証がつながるまで一般公開は禁止する。04を他計画UI完成待ちにせず、相互UI接続は後段で行う。

### 04所有のバックエンド契約

- 【新規提案・既存ファイル内に追加】`AccessScope`、`resolve_access_scope(user, now)`、`intersect_prefectures(scope, requested)`、`validate_prefecture_selection(user, selected)` を `utils/plan_gate.py` に置く。他計画は同名の独自型を定義しない。
- `AccessScope` はDBから再取得した有効利用者の `user_id`、`allowed_prefectures`（2桁コードの不変集合）、`features`（許可機能の不変集合）、`announcement_from`（過去日数制限の下限、制限なしはNone）を持つ。課金上限が必要な利用側には既存 `get_user_limits` と同じ解決結果を渡す。返却に生のStripe ID・支払情報を含めない。
- 認証済み本人のDB情報だけから解決する。クライアントの `user_id/plan/allowed_prefectures` は権限入力として採用しない。ユーザー不明・無効・プラン不明・有料契約の失効・不正な選択JSONは拒否側へ倒す。無料プランの既知状態と期限内trialの扱いは表で試験し、未知状態をPROへ昇格させない。
- 地域は `01`〜`47` の明示集合。全国権限は47コードの集合とし、空集合/Noneを全国の符号に使わない。単一/二地域は保存済み選択のうち妥当な集合だけ。未選択は閲覧0地域で、選択画面へ誘導する。
- 要求地域が未指定なら許可集合、指定ありなら要求集合と許可集合の積集合。積集合が空なら一覧は0件、詳細は範囲外として扱う。ページング、total、集計、CSV、保存検索配送、関連データ検索より前に適用する。NULL/不明地域のレコードは範囲内だと立証できなければ提供しない。
- `announcement_from` がある場合は要求開始日と権限下限の遅い方を使う。開始日省略で日数制限が消えない。金額・落札率・予測スコアをこの契約で解釈しない。
- `features` は既存PlanConfigの能力を一元化し、検索/保存/通知/API/export/prediction/運用指標を明示する。既存表にない保存・通知・運用指標の商用可否は未承認として既定拒否、隔離試験では明示fixtureで許可する。運用指標は課金上位だけで自動許可せず、既存ロール権限も確認する。
- 01所有のSearchCriteria v1は `keyword, exclude_keywords, use_or, prefecture, organization, bid_type, announcement_from/to`。06は `budget_min/max, qualification_keywords, deadline_from/to, deliverables_keyword, sort_column/direction` を任意追加する。返却は `results,total,offset,limit`。条件は既存 `SavedSearch.criteria_json` に保存し、旧 `use_not/mobile_ui` 等の変換は01の互換アダプターへ集約する。

### 価格・決済・Webhook契約

- 5,000/8,000/24,800円と「税抜」は旧提案であり、現行コードに同額があっても承認済み事実ではない。価格・税・旧standardの移行・契約発効日を承認するまで、実Checkoutと料金変更はサーバー側で無効。Price ID設定済みだけでは解除しない。
- 既存契約は明示承認なしにnationalへ読み替えず、旧standardのID/履歴を保持する。次回更新時反映の現行処理を守り、予約時には利用者の現行plan/地域を変えない。
- 検証済みWebhookのevent IDを一意に記録し、関連する契約ID・イベント時刻・処理状態を保持する。顧客IDと契約IDの一致を確認し、古い/別契約イベントで権限を復活させない。イベント時刻だけを完全な順序保証とみなさず、同時刻や矛盾イベントは保留して権限拡大しない。
- 処理済み記録とUser更新は同じDBtransactionでcommitする。未処理/保留/失敗を成功済みと混同しない。照合を要する場合は既存Stripe取得処理の範囲に限定し、試験は常にモック、実照合は別運用承認とする。

## 実装ステップ

### ステップ 1: 権限試験の基準fixtureを隔離する
- **対象**: 【既存】`tests/billing/test_plan_gate_and_webhook.py`、`tests/billing/test_billing_ui.py`、参照 `tests/conftest.py`。
- **作業**:
  1. 既存SimpleNamespace/モックを維持し、active、subscription_status、trial期限、固定nowを持つ利用者fixtureへ拡張する。
  2. DBが必要なWebhook試験はtmp_path/in-memoryへ限定し、設定読込前に試験環境を注入する。Stripe、HTTP、SMTPを遮断する。
  3. 無料、単一、二地域、全国、旧standard、PRO、未知プラン、無効利用者の期待表を試験パラメータとして置く。
- **確認**: fixture作成時のStripe/外部呼出0、永続DBへの接続0。固定時刻2026-09-17T00:00:00Zを使い、実時計に依存しない結果を得る。
- **完了条件**: `tests/conftest.py:12-21` の永続DB設定を避ける前提が確認され、後続の単体試験を安全に準備できる。
- **工数目安**: 3時間（fixture1時間、遮断1時間、期待表/確認1時間）。

### ステップ 2: UI非依存のscope型を定義する
- **対象**: 【既存】`utils/plan_gate.py`、`tests/billing/test_plan_gate_and_webhook.py`。
- **作業**:
  1. 上記 `AccessScope` と拒否結果/ドメイン例外を同じ既存ファイルに定義する。
  2. scopeの関数からStreamlit session_state、st.stop、HTTP例外を呼ばないようにし、既存デコレーターを薄い表示側に残す。
  3. 明示的なuserとnowを引数にする入口を追加し、不明userや不完全fixtureを暗黙の無料/全国にしない。
- **確認**: Streamlitランタイムなしで関数を呼べる。user=Noneとis_active=Falseでは許可scopeを返さない。scopeの地域集合は呼出後に変更できない。
- **完了条件**: 01/02/07が同じ型を注入でき、画面の操作で権限解決結果を上書きできない。
- **工数目安**: 3時間（型1時間、依存分離1時間、単体試験1時間）。

### ステップ 3: 契約状態から有効権限を解決する
- **対象**: 【既存】`utils/plan_gate.py`、`services/billing_service.py`、`config.py`、`tests/billing/test_plan_gate_and_webhook.py`。
- **作業**:
  1. 有効プラン・機能・日数下限を一つの解決経路にまとめ、旧 `get_effective_plan/get_user_limits` と矛盾しないよう委譲する。
  2. trialのUTC期限を固定nowと比較し、naive/aware日時はDB規約に合わせ境界で正規化する。past_due/canceled/未知有料状態は権限を拡大しない。
  3. 既存の機能表とPlanConfigの上限を照合し、旧standardを欠落させない。未承認の追加機能は既定拒否にする。
- **確認**: 期限直前の明示trialは定義した能力、期限同時刻以降はtrial能力なし。past_dueのPROにAPI/predictionを許可しない。無料search_days=7では公告下限が固定nowの定義に一致する。
- **完了条件**: 状態×プランの表が単体試験で固定され、時刻比較例外や未知状態による昇格がない。
- **工数目安**: 4時間（状態表1時間、実装1.5時間、境界試験1.5時間）。

### ステップ 4: 地域選択と閲覧の判定を分離する
- **対象**: 【既存】`utils/plan_gate.py`、`tests/billing/test_plan_gate_and_webhook.py`。
- **作業**:
  1. 保存済み地域JSONを配列/2桁コード/重複/上限で検証し、選択更新の妥当性判定を閲覧判定と別関数にする。
  2. 全国は明示47件、未選択は空集合として返し、`can_access_prefecture` を許可集合への所属判定にする。
  3. 要求集合との積集合と公告下限の組合せを共通契約として確定し、旧「枠が空いていれば閲覧可」試験を選択可/閲覧不可へ分ける。
- **確認**: 二地域で保存 `["13"]` の場合、27の追加選択は可能だが27閲覧は不可。要求 `["13","27"]` と許可 `["13"]` は13だけ。空選択、`["99"]`、JSON文字列は全国を返さない。
- **完了条件**: ステップ1〜4の契約を01へ渡せる。01の検索・UI完成やStripe承認を待たずに完了判定する。
- **工数目安**: 4時間（選択検証1時間、積集合1時間、境界/回帰試験2時間）。

### ステップ 5: 決済の承認停止をサーバー側に追加する
- **対象**: 【既存】`config.py`、`services/billing_service.py`、`tests/billing/test_billing_ui.py`。
- **作業**:
  1. 既存設定内へ既定falseの課金有効化設定を追加し、価格・税・旧契約移行・反映時刻の承認が解除条件であることを本計画内のゲートに固定する。
  2. Checkoutと有料価格変更のサービス入口で停止設定を確認し、Price ID存在だけでStripeを呼ばない。既存の請求閲覧/解約運用まで無断で削除しない。
  3. 未承認状態では金額を確定販売価格として返さず、旧standardからnationalへの自動移行を行わない。
- **確認**: 有効なダミーPrice IDがあっても承認停止falseの既定状態でCheckout/SubscriptionSchedule呼出0。試験で明示解除した場合だけモック1回。旧standard値は不変。
- **完了条件**: UIを経由しない呼出でも未承認の料金契約を作れない。実価格作成は手順に含めない。
- **工数目安**: 3時間（設定/入口1時間、互換範囲1時間、試験1時間）。

### ステップ 6: 地域設定画面をバックエンド検証へ接続する
- **対象**: 【既存】`app_billing.py`、`utils/plan_gate.py`、`tests/billing/test_billing_ui.py`。
- **作業**:
  1. 既存multiselectを保持し、保存transaction内で認証済みIDのUserを再取得する。
  2. 最新planとscopeで選択を再検証してから保存し、画面表示時の古いlimitを信頼しない。
  3. 未選択では閲覧不可であること、未承認価格は提案であることを表示し、停止中の有料決済ボタンを無効化する。
- **確認**: 表示時dual、保存時singleへ変更したfixtureで2地域保存を拒否しDB不変。正常な13保存は1回commit。未承認時は「税抜の確定料金」と断定せず決済呼出0。
- **完了条件**: UIのmax_selectionsを迂回してもサービス検証が働き、現行ユーザーの既存UI操作を必要以上に書き直さない。
- **工数目安**: 3時間（再取得/検証1時間、表示1時間、モック試験1時間）。

### ステップ 7: 次回更新時の契約予約を回帰保護する
- **対象**: 【既存】`services/billing_service.py`、`tests/billing/test_plan_gate_and_webhook.py`。
- **作業**:
  1. 現行SubscriptionScheduleの二phase構造とcustomer/status/item/schedule検証を読み、追加機能を作らずモック期待値にする。
  2. 予約前後でlocal planと地域を変更しないこと、freeへの変更は期末解約予約であることを検証する。
  3. schedule更新失敗時のrelease、顧客不一致、期間不足、予約重複時の例外を限定したドメイン結果へ整理する。
- **確認**: single→dualの予約で現行phaseは元Price、次phaseだけ新Price、local planはsingleのまま。失敗モック時release1回、予約済みならcreate0回。
- **完了条件**: 利用者が実装した次回反映方式を保持し、即時権限変更や実Stripe操作を追加しない。
- **工数目安**: 4時間（正常契約1時間、例外整理1時間、回帰試験2時間）。

### ステップ 8: Webhookイベントの永続処理記録を追加する
- **対象**: 【既存】`database/models/_generated.py`、`database/repositories/__init__.py`、`services/billing_service.py`、`tests/billing/test_plan_gate_and_webhook.py`。【新規提案】Webhook台帳migration。
- **作業**:
  1. event IDの一意キー、customer/subscription参照、event時刻、処理状態を持つ最小記録を既存DBへ追加する。生payloadや秘密は不要に保存しない。
  2. 実装時のmigration headを確認して追記migrationを用意し、Userと選択地域を再作成しない。
  3. 一時DBで同一イベントの並行登録とrollbackを検証する。BaseRepositoryの内部commitは台帳transactionでは使わない。
- **確認**: 同じevent IDが同時に2回来ても処理対象は1件。記録後に故障を入れれば成功済みにならない。migration前後で既存User/plan/地域JSONが一致する。
- **完了条件**: プロセス再起動後も重複判定でき、メモリ集合だけに依存しない。
- **工数目安**: 4時間（台帳1時間、migration1時間、一時DB/競合試験2時間）。

### ステップ 9: Webhookの再送と順序逆転を安全に扱う
- **対象**: 【既存】`app_webhook.py`、`services/billing_service.py`、`tests/billing/test_plan_gate_and_webhook.py`。
- **作業**:
  1. 既存署名検証を維持し、検証済みイベントだけ台帳と処理へ渡す。未知イベントは権限変更なしで明示分類する。
  2. customerと現在subscriptionの一致、event ID、時刻、処理状態を確認する。古い別契約や矛盾した同時刻イベントは保留し、権限を増やさない。
  3. 台帳の成功確定とUser更新を一transactionにし、DB失敗はrollbackして再送で回復できるようにする。
  4. 状態照合が必要な経路は既存取得呼び出しを注入可能にしてモック化し、照合失敗を成功扱いしない。
- **確認**: 同一署名済みfixtureの再送で更新1回。新しい解約イベント後の古いactiveイベントで有料権限が復活しない。同時刻矛盾は保留。User更新後の故障では台帳成功とUser変更の両方をrollbackする。
- **完了条件**: event.createdだけを絶対順序とせず、別契約・再送・故障の保守的な状態遷移が固定される。攻撃の実演や実ネットワーク試験は行わない。
- **工数目安**: 6時間（小作業1: dispatch/一意処理と試験2時間、小作業2: 時系列/契約照合と試験2時間、小作業3: transaction故障試験2時間）。

### ステップ 10: 地域縮小と旧契約互換を回帰保護する
- **対象**: 【既存】`services/billing_service.py`、`tests/billing/test_plan_gate_and_webhook.py`。
- **作業**:
  1. `230-239` 行の「旧planを保持→選択縮小→新plan設定」の現行順序を維持し、同一イベント再適用を試験する。
  2. 縮小時の保持コードを昇順先頭N件の現行方針にそろえ、未承認のアクセス頻度推定や新しい優先度を導入しない。
  3. 全国/旧standard→限定、選択なし、不正JSON、解約、trial終了を試験し、余剰地域を以降のscopeへ残さない。
- **確認**: dual `["13","27"]`→singleで13だけ保持し、同イベント再処理で変化なし。nationalから限定で選択なしなら空集合。旧standardの既知Priceは勝手にnationalへ名称変更しない。
- **完了条件**: 修正済み実装を後退させず、現行契約の変更とscope更新が同じ結果を返す。
- **工数目安**: 3時間（既存回帰1時間、境界追加1時間、確認1時間）。

### ステップ 11: 利用側へ渡す権限契約をモックで検証する
- **対象**: 【既存】`utils/plan_gate.py`、`tests/billing/test_plan_gate_and_webhook.py`。他計画実装は編集しない。
- **作業**:
  1. 検索・詳細・export・保存検索配送・APIの各利用側を模した小さな契約試験を追加する。
  2. scopeがない呼出、空地域、要求地域未指定、契約変更後の再解決、日付省略時の下限を確認する。
  3. UIデコレーターとバックエンド解決が同じ許可/拒否を示すか比較する。共通型の署名を後段計画へ渡す。
- **確認**: 許可13/要求13,27では全利用側で13のみ。権限消失後の配送モックは0。無料下限より古い公告はフィルタ対象外。一般利用者は運用指標を取得できない。
- **完了条件**: 実APIや検索UIなしで04単体の契約が完了し、UI接続待ちの循環依存がない。
- **工数目安**: 3時間（契約fixture1時間、利用側試験1時間、照合1時間）。

### ステップ 12: 権限完成と課金公開可否を別々に判定する
- **対象**: 【既存】`tests/billing/test_plan_gate_and_webhook.py`、`tests/billing/test_billing_ui.py`、本計画の完了ゲート。
- **作業**:
  1. 権限単体・予約・再送・逆順・地域縮小の期待表を回帰結果と照合する。
  2. 価格、税、旧standard移行、反映日、請求ポータルの変更可能範囲が承認済みかを本計画のゲートで個別判定する。未承認項目は未承認のまま残す。
  3. 隔離データで機能停止と既存契約再読込を確認し、04の権限契約だけを01/07へ渡す。
- **確認**: 権限試験が完成していても承認停止中のCheckoutは呼出0。停止後も既存契約履歴と選択地域を読み出せる。Webhook台帳を消して再送可能状態に戻さない。
- **完了条件**: 「権限契約の実装完了」と「本番課金開始可」を混同せず、本番リリースを自動実行しない。
- **工数目安**: 3時間（回帰照合1時間、承認項目1時間、停止/復旧試験1時間）。

## 関連試験・静的解析

- この文書改訂では試験、インストール、Stripe、サービス起動を実行しない。`tests/conftest.py:12-21` が永続 `tests/fixtures/test.db` を強制するため、隔離確認前のpytestは禁止。
- ステップ1で全fixtureの自己完結と通信遮断を確認した後のみ、候補コマンドは `pytest --noconftest tests/billing/test_plan_gate_and_webhook.py tests/billing/test_billing_ui.py -q`。DB追加試験もtmp_path/in-memoryを明示する。共通fixtureに依存する状態ならフラグを使わず基盤の隔離完了を待つ。
- `.github/workflows/test.yml:18-20` の静的解析コマンドは `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`、`mypy .`。2026-09-17の共有結果ではflake8が `AttributeError: EntryPoints.get` で停止し、mypyはcommand not found。基準結果は取得不能で、コード合格とは扱わない。依存導入や環境変更は別承認。
- 最低限の期待表: 選択可/閲覧不可の区別、0/1/2/47地域、旧standard、無料期限、trial境界、無効利用者、失効契約、承認停止、予約失敗、重複event、時刻逆転、同時刻矛盾、別契約、DBrollback。

## ロールバック

1. 有料Checkout/価格変更のサーバー側停止を維持し、UIだけを戻して決済可能にしない。請求確認/解約に必要な既存運用経路は別途確認して保持する。
2. scopeの問題で旧「空き枠なら閲覧可」へ戻さない。問題の機能を停止してfail-closedを維持する。必要なら最後に確認済みの権限解決版に限定して戻す。
3. 追加台帳は保持し、Userとイベントの処理済み情報を消さない。pending/保留は範囲を決めて照合するまで反映しない。
4. 実際の契約操作が別承認で行われた後は、コードrollbackだけでStripe契約が元に戻るとは考えない。外部契約照合と顧客別対処を別の運用承認で行う。本計画の隔離試験で実決済を巻き戻さない。

## 完了ゲート（本番開始は別承認）

- 04所有のscope型・地域積集合・機能と日数下限・未知状態拒否を01/02/07が共有できる。個人IDは認証済みDB情報だけから取得する。
- 既存User/地域列/利用者の修正済みWebhook順序/次回予約を保持し、モックで正常・異常・replayを確認した。
- 価格/税/旧契約移行/請求ポータルからの変更範囲が未承認なら実課金は無効のまま。実StripeのPrice作成、実Checkout、実契約変更、本番migrationを自動実行しない。
- 07のJWT/認証接続、利用側scope適用、静的解析基準未取得が残れば一般公開不可。計画書完成を運用安全性の証明とはしない。
