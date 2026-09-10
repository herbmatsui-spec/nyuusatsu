# 認証・課金基盤 実装計画書（24ステップ）

> 目的：Flask-Login + Stripe Billing（Stripe Connectではない）で「無料トライアル→有料プラン移行→顧客ポータル」を最小構成で実装
> 前提：既存 `config/AppConfig`、`database/models/user.py`、`database/engine.py`、`services/auth_service.py` が存在
> 制約：低性能LLMでも実装可能なよう、1タスク＝1ファイル編集または1関数追加の粒度に分割

---

## Phase A: データモデル・設定拡張（ステップ 1〜6）

### Step 1: プラン定義を `config/__init__.py` に追加
- `config/__init__.py` を開く
- `AppConfig` クラス内に以下を追加：
  ```python
  class PlanConfig:
      FREE = "free"
      STANDARD = "standard"
      PRO = "pro"
      ENTERPRISE = "enterprise"

      LIMITS = {
          FREE: {"search_days": 7, "pdf_extract_daily": 10, "api_requests_monthly": 0, "export": False},
          STANDARD: {"search_days": None, "pdf_extract_daily": None, "api_requests_monthly": 1000, "export": True},
          PRO: {"search_days": None, "pdf_extract_daily": None, "api_requests_monthly": 10000, "export": True},
          ENTERPRISE: {"search_days": None, "pdf_extract_daily": None, "api_requests_monthly": 100000, "export": True},
      }
      PRICES = {  # 月額（円）
          FREE: 0,
          STANDARD: 30000,
          PRO: 80000,
          ENTERPRISE: 200000,
      }
      STRIPE_PRICE_IDS = {  # Stripeダッシュボードで作成後のIDを.envで上書き
          STANDARD: os.getenv("STRIPE_PRICE_STANDARD", "price_standard"),
          PRO: os.getenv("STRIPE_PRICE_PRO", "price_pro"),
          ENTERPRISE: os.getenv("STRIPE_PRICE_ENTERPRISE", "price_enterprise"),
      }
  ```
- `AppConfig` に `plan = PlanConfig()` を追加

### Step 2: Userモデルに課金関連カラム追加（`database/models/user.py`）
- `database/models/user.py` を開く
- `User` クラスに以下カラム追加：
  ```python
  plan: Mapped[str] = mapped_column(String(20), default=PlanConfig.FREE, nullable=False)
  stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
  stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
  trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
  subscription_status: Mapped[str] = mapped_column(String(20), default="inactive", nullable=False)  # active/trialing/past_due/canceled
  current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
  ```
- import に `datetime`、`Optional`、`mapped_column`、`String`、`DateTime` 追加

### Step 3: Alembicマイグレーション生成・実行
- ターミナルで実行：
  ```bash
  alembic revision --autogenerate -m "add billing columns to users"
  alembic upgrade head
  ```
- 生成されたファイル確認：`plan` が NOT NULL DEFAULT 'free'、`stripe_customer_id` 等が NULL 許容

### Step 4: 環境変数テンプレート更新（`.env.example`）
- 以下を追加：
  ```
  STRIPE_SECRET_KEY=sk_test_xxx
  STRIPE_PUBLISHABLE_KEY=pk_test_xxx
  STRIPE_WEBHOOK_SECRET=whsec_xxx
  STRIPE_PRICE_STANDARD=price_xxx
  STRIPE_PRICE_PRO=price_xxx
  STRIPE_PRICE_ENTERPRISE=price_xxx
  STRIPE_SUCCESS_URL=http://localhost:8501/billing/success
  STRIPE_CANCEL_URL=http://localhost:8501/billing/cancel
  STRIPE_PORTAL_URL=http://localhost:8501/billing/portal
  ```

### Step 5: Stripeクライアント初期化ユーティリティ作成（`utils/stripe_client.py` 新規）
```python
import stripe
from config import AppConfig

_config = AppConfig()

def get_stripe_client() -> stripe.StripeClient:
    return stripe.StripeClient(_config.stripe.secret_key)

def get_stripe_sync() -> stripe.StripeClient:
    """同期版（Flask/Streamlit用）"""
    stripe.api_key = _config.stripe.secret_key
    return stripe
```

### Step 6: 設定クラスにStripe設定追加（`config/__init__.py`）
- `AppConfig` 内に `stripe` プロパティ追加：
  ```python
  @property
  def stripe(self):
      class StripeConfig:
          secret_key = os.getenv("STRIPE_SECRET_KEY")
          publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY")
          webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
          success_url = os.getenv("STRIPE_SUCCESS_URL")
          cancel_url = os.getenv("STRIPE_CANCEL_URL")
          portal_url = os.getenv("STRIPE_PORTAL_URL")
      return StripeConfig()
  ```

---

## Phase B: 認証・セッション管理（ステップ 7〜10）

### Step 7: Flask-Loginユーザーローダー実装（`services/auth_service.py` 修正）
- `AuthService` クラスにメソッド追加：
  ```python
  def load_user(self, user_id: str) -> Optional[User]:
      return self.session.query(User).filter(User.id == int(user_id)).first()

  def get_user_by_stripe_customer(self, customer_id: str) -> Optional[User]:
      return self.session.query(User).filter(User.stripe_customer_id == customer_id).first()
  ```

### Step 8: ログイン・登録フォーム統合（`app.py` 修正）
- `show_login_screen()` 内に「アカウント作成」タブ追加
- 登録時：`AuthService.create_user()` 呼び出し → 自動で `plan="free"`、`trial_ends_at=now()+7days` 設定
- 登録完了後：Stripe顧客作成（Step 11 で実装）を同期呼び出し

### Step 9: セッション管理ミドルウェア（`utils/auth_decorator.py` 修正）
- `is_authenticated()` にプラン有効性チェック追加：
  ```python
  def is_authenticated() -> bool:
      if not st.session_state.get("authenticated"):
          return False
      # 有料プランの期限切れチェック
      user = get_current_user()
      if user and user.plan != PlanConfig.FREE:
          if user.current_period_end and user.current_period_end < datetime.utcnow():
              return False
      return True
  ```

### Step 10: 現在ユーザー取得ヘルパー（`utils/auth_decorator.py` に追加）
```python
def get_current_user() -> Optional[User]:
    if not st.session_state.get("authenticated"):
        return None
    from database.engine import get_session
    from services.auth_service import AuthService
    from config import AppConfig
    with get_session() as session:
        auth = AuthService(session, AppConfig())
        return auth.get_user_by_username(st.session_state.get("username"))
```

---

## Phase C: Stripe連携・チェックアウト（ステップ 11〜15）

### Step 11: Stripe顧客作成関数（`services/billing_service.py` 新規）
```python
from utils.stripe_client import get_stripe_sync
from database.models.user import User
from config import AppConfig

_config = AppConfig()

def create_stripe_customer(user: User) -> str:
    """ユーザー登録時にStripe Customerを作成し、customer_idを返す"""
    stripe = get_stripe_sync()
    customer = stripe.Customer.create(
        email=user.email,
        name=user.username,
        metadata={"user_id": str(user.id)}
    )
    user.stripe_customer_id = customer.id
    return customer.id

def ensure_stripe_customer(user: User) -> str:
    """既存customer_idがあれば返し、なければ作成"""
    if user.stripe_customer_id:
        return user.stripe_customer_id
    return create_stripe_customer(user)
```

### Step 12: チェックアウトセッション作成（`services/billing_service.py` 追加）
```python
def create_checkout_session(user: User, plan: str) -> str:
    """Stripe Checkout Sessionを作成し、URLを返す"""
    stripe = get_stripe_sync()
    customer_id = ensure_stripe_customer(user)
    price_id = _config.plan.STRIPE_PRICE_IDS.get(plan)
    if not price_id:
        raise ValueError(f"Invalid plan: {plan}")

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=_config.stripe.success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=_config.stripe.cancel_url,
        subscription_data={
            "trial_period_days": 0 if user.plan != PlanConfig.FREE else 7,
            "metadata": {"user_id": str(user.id), "plan": plan}
        },
        allow_promotion_codes=True,
    )
    return session.url
```

### Step 13: 顧客ポータルセッション作成（`services/billing_service.py` 追加）
```python
def create_portal_session(user: User) -> str:
    """Stripe Billing Portalセッション作成"""
    stripe = get_stripe_sync()
    customer_id = ensure_stripe_customer(user)
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=_config.stripe.portal_url,
    )
    return session.url
```

### Step 14: Streamlit課金ページ作成（`app_billing.py` 新規）
```python
import streamlit as st
from utils.auth_decorator import is_authenticated, get_current_user
from services.billing_service import create_checkout_session, create_portal_session
from config import AppConfig, PlanConfig

def render():
    if not is_authenticated():
        st.error("ログインしてください")
        st.stop()

    user = get_current_user()
    st.title("💳 プラン・請求管理")

    # 現在のプラン表示
    col1, col2, col3 = st.columns(3)
    col1.metric("現在のプラン", user.plan.upper())
    col2.metric("月額料金", f"¥{PlanConfig.PRICES.get(user.plan, 0):,}")
    if user.current_period_end:
        col3.metric("次回更新日", user.current_period_end.strftime("%Y-%m-%d"))

    st.divider()

    # プラン選択・アップグレード
    st.subheader("プラン変更")
    plans = [PlanConfig.FREE, PlanConfig.STANDARD, PlanConfig.PRO, PlanConfig.ENTERPRISE]
    current_idx = plans.index(user.plan) if user.plan in plans else 0

    for plan in plans:
        if plan == user.plan:
            st.info(f"✅ {plan.upper()}（現在のプラン） - ¥{PlanConfig.PRICES[plan]:,}/月")
            continue
        if plans.index(plan) <= current_idx:
            st.caption(f"⬇ {plan.upper()} - ¥{PlanConfig.PRICES[plan]:,}/月（ダウングレードは次回更新時）")
        else:
            if st.button(f"⬆ {plan.upper()} にアップグレード - ¥{PlanConfig.PRICES[plan]:,}/月", key=f"upgrade_{plan}"):
                url = create_checkout_session(user, plan)
                st.markdown(f"[決済ページへ進む]({url})", unsafe_allow_html=True)

    st.divider()

    # 請求ポータル
    st.subheader("請求書・支払い方法管理")
    if st.button("📄 Stripe請求ポータルを開く"):
        url = create_portal_session(user)
        st.markdown(f"[請求ポータルへ]({url})", unsafe_allow_html=True)
```

### Step 15: `app.py` サイドバーに課金メニュー追加
- `app.py` のサイドバー（認証後表示エリア）に追加：
  ```python
  if st.button("💳 プラン・請求", use_container_width=True):
      st.switch_page("app_billing.py")
  ```

---

## Phase D: Webhook・サブスクリプション同期（ステップ 16〜19）

### Step 16: Webhookエンドポイント作成（`app_webhook.py` 新規・FastAPI推奨）
```python
from fastapi import FastAPI, Request, Header, HTTPException
import stripe
from config import AppConfig
from database.engine import get_session
from services.billing_service import handle_webhook_event

_config = AppConfig()
stripe.api_key = _config.stripe.secret_key
app = FastAPI()

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, _config.stripe.webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    handle_webhook_event(event)
    return {"status": "ok"}
```

### Step 17: Webhookハンドラ実装（`services/billing_service.py` 追加）
```python
from database.engine import get_session
from database.models.user import User
from config import PlanConfig
from datetime import datetime

def handle_webhook_event(event: dict):
    """Stripe Webhookイベントを処理し、Userレコードを更新"""
    event_type = event["type"]
    data = event["data"]["object"]

    with get_session() as session:
        if event_type == "checkout.session.completed":
            handle_checkout_completed(session, data)
        elif event_type == "customer.subscription.created":
        elif event_type == "customer.subscription.updated":
            handle_subscription_updated(session, data)
        elif event_type == "customer.subscription.deleted":
            handle_subscription_canceled(session, data)
        elif event_type == "invoice.payment_failed":
            handle_payment_failed(session, data)
        session.commit()

def handle_checkout_completed(session, session_obj):
    user_id = session_obj.get("metadata", {}).get("user_id")
    if user_id:
        user = session.query(User).filter(User.id == int(user_id)).first()
        if user:
            user.stripe_subscription_id = session_obj.get("subscription")

def handle_subscription_updated(session, sub):
    customer_id = sub.get("customer")
    user = session.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return
    user.stripe_subscription_id = sub.get("id")
    user.subscription_status = sub.get("status")
    user.current_period_end = datetime.fromtimestamp(sub.get("current_period_end"))
    # プラン判定
    items = sub.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        for plan, pid in PlanConfig.STRIPE_PRICE_IDS.items():
            if pid == price_id:
                user.plan = plan
                break

def handle_subscription_canceled(session, sub):
    customer_id = sub.get("customer")
    user = session.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        user.plan = PlanConfig.FREE
        user.subscription_status = "canceled"
        user.stripe_subscription_id = None
        user.current_period_end = None

def handle_payment_failed(session, invoice):
    customer_id = invoice.get("customer")
    user = session.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        user.subscription_status = "past_due"
```

### Step 18: 無料トライアル終了判定ロジック（`services/billing_service.py` 追加）
```python
def is_trial_active(user: User) -> bool:
    """無料トライアル期間中か判定"""
    if user.plan != PlanConfig.FREE:
        return False
    if user.trial_ends_at and user.trial_ends_at > datetime.utcnow():
        return True
    return False

def get_effective_plan(user: User) -> str:
    """実効プラン取得（トライアル中はPro相当扱い）"""
    if is_trial_active(user):
        return PlanConfig.PRO  # トライアル中は全機能開放
    return user.plan
```

### Step 19: プラン別機能制御ミドルウェア（`utils/plan_gate.py` 新規）
```python
from functools import wraps
from utils.auth_decorator import get_current_user
from services.billing_service import get_effective_plan
from config import PlanConfig

def require_plan(*allowed_plans):
    """Streamlitページ/関数にプラン制限を付与するデコレータ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                st.error("ログインが必要です")
                st.stop()
            effective = get_effective_plan(user)
            if effective not in allowed_plans:
                st.error(f"この機能は {'/'.join(allowed_plans)} プラン以上で利用できます")
                st.info("👉 [プラン・請求ページ](app_billing.py) からアップグレードしてください")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator

# 使用例：
# @require_plan(PlanConfig.STANDARD, PlanConfig.PRO, PlanConfig.ENTERPRISE)
# def export_csv(): ...
```

---

## Phase E: 顧客ポータル・ダッシュボード統合（ステップ 20〜24）

### Step 20: ダッシュボードにプラン表示追加（`app_dashboard.py` 修正）
- サイドバーに現在プラン表示：
  ```python
  from utils.auth_decorator import get_current_user
  from services.billing_service import get_effective_plan, is_trial_active
  from config import PlanConfig

  user = get_current_user()
  if user:
      effective = get_effective_plan(user)
      if is_trial_active(user):
          st.sidebar.success(f"🎁 無料トライアル中（{effective.upper()}相当）")
      else:
          st.sidebar.info(f"📋 プラン: {effective.upper()}")
  ```

### Step 21: 検索機能にプラン制限適用（`app_dashboard.py` の検索タブ修正）
- 検索実行ボタンの前にガード追加：
  ```python
  from utils.plan_gate import require_plan

  @require_plan(PlanConfig.FREE, PlanConfig.STANDARD, PlanConfig.PRO, PlanConfig.ENTERPRISE)
  def render_search():
      # 既存の検索ロジック
      # 無料プランは search_days=7 に制限
      user = get_current_user()
      effective = get_effective_plan(user)
      limits = PlanConfig.LIMITS[effective]
      if limits["search_days"]:
          # フィルタに「作成日 >= 7日前」を強制追加
          pass
  ```

### Step 22: PDF抽出機能に日次上限適用（`app.py` 修正）
- アップロード処理前にチェック：
  ```python
  from utils.plan_gate import require_plan
  from services.billing_service import get_effective_plan
  from config import PlanConfig
  from datetime import date
  from database.repositories.extraction_result_repository import ExtractionResultRepository

  @require_plan(PlanConfig.FREE, PlanConfig.STANDARD, PlanConfig.PRO, PlanConfig.ENTERPRISE)
  def process_pdf():
      user = get_current_user()
      effective = get_effective_plan(user)
      daily_limit = PlanConfig.LIMITS[effective]["pdf_extract_daily"]
      if daily_limit:
          repo = ExtractionResultRepository()
          today_count = repo.count_by_user_today(user.id, date.today())
          if today_count >= daily_limit:
              st.error(f"本日の抽出上限（{daily_limit}件）に達しました")
              st.stop()
  ```

### Step 23: APIリクエスト数カウント・制限（`services/api_usage.py` 新規）
```python
from database.engine import get_session
from database.models.api_usage import ApiUsage  # 要作成：Step 24で
from datetime import date, datetime
from config import PlanConfig
from utils.auth_decorator import get_current_user

def check_api_limit() -> bool:
    """APIリクエスト上限チェック。超過ならFalse"""
    user = get_current_user()
    if not user:
        return False
    effective = get_effective_plan(user)
    monthly_limit = PlanConfig.LIMITS[effective]["api_requests_monthly"]
    if monthly_limit is None or monthly_limit <= 0:
        return False  # 無制限または利用不可

    with get_session() as session:
        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = session.query(ApiUsage).filter(
            ApiUsage.user_id == user.id,
            ApiUsage.month == current_month
        ).first()
        count = usage.count if usage else 0
        return count < monthly_limit

def increment_api_usage():
    """API使用回数インクリメント"""
    user = get_current_user()
    if not user:
        return
    with get_session() as session:
        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = session.query(ApiUsage).filter(
            ApiUsage.user_id == user.id,
            ApiUsage.month == current_month
        ).first()
        if usage:
            usage.count += 1
        else:
            usage = ApiUsage(user_id=user.id, month=current_month, count=1)
            session.add(usage)
        session.commit()
```

### Step 24: API使用量テーブル作成（`database/models/api_usage.py` 新規 + マイグレーション）
```python
# database/models/api_usage.py
from sqlalchemy import DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from database.base import Base

class ApiUsage(Base):
    __tablename__ = "api_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    month: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "month", name="uq_api_usage_user_month"),
    )
```
- マイグレーション実行：
  ```bash
  alembic revision --autogenerate -m "create api_usage table"
  alembic upgrade head
  ```

---

## 実装順序の依存関係グラフ

```
Step 1,2,3,4,5,6  →  Step 7,8,9,10  →  Step 11,12,13  →  Step 14,15
                                                                    ↓
Step 24  ←  Step 23  ←  Step 22,21,20  ←  Step 16,17,18,19
```

---

## テストチェックリスト（実装後確認）

| # | テスト項目 | 確認方法 |
|---|------------|----------|
| 1 | 新規登録→無料トライアル7日付与 | 登録後 `trial_ends_at` が7日後、`plan="free"` |
| 2 | 無料プランで検索→7日以内のみ表示 | ダッシュボード検索で古い案件が出ない |
| 3 | 無料プランでPDF抽出→日次10件制限 | 11件目でエラー表示 |
| 4 | Stripe CheckoutでStarter契約→Webhookでplan更新 | Stripeテストモードで決済→DB確認 |
| 5 | Starterプランで全期間検索・CSV出力可 | 検索タブ・CSVボタン動作 |
| 6 | StarterプランでAPI月1000回まで可 | API叩いてカウント増加・1001回目で429 |
| 7 | 請求ポータルで支払い方法変更可 | `app_billing.py` から遷移 |
| 8 | サブスク解約→次回更新日でFreeに戻る | Stripeテストで解約→Webhook処理確認 |
| 9 | 支払い失敗→past_due→機能制限 | Stripeテストで失敗→ステータス確認 |
| 10 | ダウングレード→次回更新時適用 | Pro→Standard変更→即時Pro維持、更新日で切替 |

---

## 推定工数（低性能LLM前提：1ステップ＝1プロンプト・1ファイル編集）

| フェーズ | ステップ数 | 目安時間 |
|----------|-----------|----------|
| Phase A: モデル・設定 | 6 | 3-4時間 |
| Phase B: 認証拡張 | 4 | 2-3時間 |
| Phase C: Stripe連携 | 5 | 4-5時間 |
| Phase D: Webhook | 4 | 3-4時間 |
| Phase E: 統合・制御 | 5 | 3-4時間 |
| **合計** | **24** | **15-20時間** |

---

## 最小動作セット（最初に動くものだけ）

優先度高（まずこれだけで「無料登録→トライアル→有料決済→機能制限」が回る）：
1. Step 1,2,3,4,5,6（モデル・設定）
2. Step 7,8,10（認証・ユーザー取得）
3. Step 11,12（Stripe顧客・Checkout）
4. Step 14（課金ページ）
5. Step 16,17（Webhook・同期）
6. Step 18,19（プラン判定・制御デコレータ）
7. Step 20,21（ダッシュボード統合・検索制限）

残り（Step 9,13,15,22,23,24）は後回し可。