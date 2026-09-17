# 料金プラン

地域別料金プラン（改善案 4）の詳細。nsearch.jp の都道府県別プランを参考に、ライトユーザー向けの低価格プランを提供する。

## プラン一覧（税抜）

| プラン | 月額 | アクセス可能都道府県 | 検索期間 | PDF抽出 | API リクエスト | CSV/JSON出力 | 備考 |
|---|---|---|---|---|---|---|---|
| Free | ¥0 | 1 | 過去1週間 | 10件/日 | 不可 | 不可 | 登録ですぐ利用可能 |
| シングル地域 | ¥5,000 | 1 | 無制限 | 無制限 | 1,000件/月 | 可 | 1都道府県に絞った利用向け |
| デュアル地域 | ¥8,000 | 2 | 無制限 | 無制限 | 1,000件/月 | 可 | nsearch.jp と同額の2県プラン |
| 全国 | ¥24,800 | 47（全県） | 無制限 | 無制限 | 10,000件/月 | 可 | 旧スタンダードと同額 |
| Pro | ¥80,000 | 47（全県） | 無制限 | 無制限 | 10,000件/月 | 可 | 予測分析・APIアクセス |
| Enterprise | ¥200,000 | 47（全県） | 無制限 | 無制限 | 100,000件/月 | 可 | 専用サポート・カスタム機能 |

## 都道府県アクセス制御

- シングル地域・デュ地域プランのユーザーは、**プラン・請求ページで都道府県を選択**する。選択は `users.allowed_prefectures`（JSON、都道府県コード "01"〜"47"）に保存される。
- 検索・クローラー設定時には `utils/plan_gate.py` の `can_access_prefecture()` が参照され、未選択枠が残っている場合は選択可能、上限に達していれば既存選択のみアクセス可。
- 検索結果は `get_search_prefecture_scope()` が解決したスコープで絞り込まれる:
  - 未ログイン / 全国 / Pro / Enterprise / 有効なトライアル → 無制限
  - シングル・デュアル地域 → 選択済み都道府県のみ
  - **選択未保存（空スコープ） → 0件**（無制限にはフォールバックしない）
- 対象は統一検索（`app_unified_search.py`）、案件検索 API（`GET /bids`, `GET /bids/{id}`, レガシー `GET /search`。Bearer トークン任意、未認証は無制限）。
- Free は 1 県のみ。選択未保存の場合は検索結果 0 件となるため、プラン・請求ページで選択を保存する。

## プラン変更の挙動

- **アップグレード**（例: シングル地域 → 全国）: 即時に都道府県制限は緩和される。決済は Stripe Checkout で実施。
- **ダウングレード**（例: 全国 → デュアル地域）: **次回更新日**に反映される（Stripe Subscription Schedule で次サイクルから新しい価格に変更。日割り請求なし）。
  - 反映時（Webhook `customer.subscription.updated`）に、選択都道府県が新プランの上限を超えていれば超過分を自動解除（コード順に保持）する。
- **キャンセル**: 次回更新日に終了し、Free プランへ戻る。選択都道府県はリセットされる。
- 既存契約があっても、未契約（Free）からの初回契約は Stripe Checkout を使用する。

## 設定方法

1. Stripe ダッシュボードで `入札システム 地域プラン` 製品を作成し、Recurring 価格（JPY）を 3 つ作成する:
   - シングル地域: 5,000 円
   - デュアル地域: 8,000 円
   - 全国: 24,800 円
2. `.env` に Price ID を設定する（`.env.example` 参照）:

   ```bash
   STRIPE_PRICE_SINGLE_REGION=price_xxx
   STRIPE_PRICE_DUAL_REGION=price_xxx
   STRIPE_PRICE_NATIONAL=price_xxx
   ```

3. マイグレーションを適用する（`users.allowed_prefectures` カラム追加）:

   ```bash
   alembic upgrade head
   ```

   本番 DB への適用手順: メンテナンス告知 → バックアップ取得 → 上記コマンド実行 → `users` テーブルに `allowed_prefectures` (TEXT, NULL許可) が追加されたことを確認。

4. Webhook エンドポイント (`app_webhook.py`) に `customer.subscription.updated` / `customer.subscription.deleted` / `invoice.payment_failed` を購読させる。

## 実装マップ

| 要素 | ファイル |
|---|---|
| プラン定義・価格・上限 | `config.py` (`PlanConfig`) |
| 都道府県ゲート（選択可否） | `utils/plan_gate.py` (`can_access_prefecture` 等) |
| 検索スコープ解決 | `utils/plan_gate.py` (`get_search_prefecture_scope`) |
| 統一検索へのスコープ適用 | `app_unified_search.py`, `services/search_service.py` (`allowed_prefectures`) |
| ダッシュボード検索 | `app_dashboard.py`（`BidService.get_all_bids(allowed_prefectures=...)` を利用可） |
| REST API スコープ適用 | `search_api/main.py` (`get_prefecture_scope`), `database/repositories/__init__.py` (`BidRepository.search(prefecture_codes=)`) |
| プラン変更（次サイクル予約） | `services/billing_service.py` (`change_subscription_plan`) |
| ダウングレード時の都道府県縮小 | `services/billing_service.py` (`adjust_prefectures_for_plan_change`, `_handle_subscription_updated`) |
| Webhook 同期 | `services/billing_service.py` (`handle_webhook_event`) |
| プラン UI・都道府県選択 | `app_billing.py` |
| テスト | `tests/billing/` |
