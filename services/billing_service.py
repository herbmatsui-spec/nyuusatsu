"""Billing service - Stripe integration and plan management."""
from datetime import datetime, timezone
from typing import Optional
import json

from config import PlanConfig
from database.models.user import User
from utils.stripe_client import get_stripe_sync


_config = None


def _get_config():
    global _config
    if _config is None:
        from config import AppConfig
        _config = AppConfig()
    return _config


def ensure_stripe_customer(user: User) -> str:
    """Ensure user has a Stripe customer ID, create if needed."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    cfg = _get_config()
    stripe = get_stripe_sync()
    customer = stripe.Customer.create(
        email=user.email or f"{user.username}@example.com",
        name=user.username,
        metadata={"user_id": str(user.id)}
    )
    user.stripe_customer_id = customer.id
    return customer.id


def create_checkout_session(user: User, plan: str) -> str:
    """Create Stripe Checkout Session for subscription upgrade."""
    cfg = _get_config()
    if user.stripe_subscription_id:
        raise ValueError("既存の契約はプラン変更から更新してください")
    price_id = cfg.plan.STRIPE_PRICE_IDS.get(plan)
    if not price_id:
        raise ValueError(f"Invalid plan: {plan}")
    stripe = get_stripe_sync()
    customer_id = ensure_stripe_customer(user)
    subscription_data = {"metadata": {"user_id": str(user.id), "plan": plan}}

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=cfg.stripe.success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cfg.stripe.cancel_url,
        metadata={"user_id": str(user.id)},
        subscription_data=subscription_data,
        allow_promotion_codes=True,
    )
    return session.url


def create_portal_session(user: User) -> str:
    """Create Stripe Billing Portal session."""
    cfg = _get_config()
    stripe = get_stripe_sync()
    customer_id = ensure_stripe_customer(user)
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=cfg.stripe.portal_url,
    )
    return session.url


def _get_plan_prefecture_limit(plan: str) -> int:
    """Get the maximum number of prefectures allowed for a plan."""
    limits = PlanConfig().LIMITS.get(plan, PlanConfig().LIMITS[PlanConfig.FREE])
    return limits.get('prefectures', 1)


def adjust_prefectures_for_plan_change(user: User, new_plan: str) -> dict:
    """
    Adjust user's selected prefectures when changing plans.
    
    Returns:
        dict with keys: 'adjusted' (bool), 'removed_prefectures' (list), 'warning' (str)
    """
    current_plan = user.plan
    current_limit = _get_plan_prefecture_limit(current_plan)
    new_limit = _get_plan_prefecture_limit(new_plan)
    
    # If upgrading or same limit, no adjustment needed
    if new_limit >= current_limit:
        return {"adjusted": False, "removed_prefectures": [], "warning": ""}
    
    # Downgrading - need to check if current prefectures exceed new limit
    if not user.allowed_prefectures:
        return {"adjusted": False, "removed_prefectures": [], "warning": ""}
    
    try:
        current_prefectures = set(json.loads(user.allowed_prefectures))
    except (json.JSONDecodeError, TypeError):
        return {"adjusted": False, "removed_prefectures": [], "warning": ""}
    
    if len(current_prefectures) <= new_limit:
        return {"adjusted": False, "removed_prefectures": [], "warning": ""}
    
    # Need to remove excess prefectures - keep first N (could be improved with priority logic)
    sorted_prefectures = sorted(current_prefectures)
    kept = set(sorted_prefectures[:new_limit])
    removed = sorted_prefectures[new_limit:]
    
    # Update user's allowed prefectures
    user.allowed_prefectures = json.dumps(list(kept))
    
    warning = f"プラン変更により、都道府県選択が {len(removed)} 件自動的に解除されました: {', '.join(removed)}"
    
    return {"adjusted": True, "removed_prefectures": removed, "warning": warning}


def change_subscription_plan(user: User, new_plan: str) -> bool:
    """Change user's subscription plan (for downgrades - takes effect at period end)."""
    if not user.stripe_subscription_id:
        raise ValueError("No active subscription found")

    cfg = _get_config()
    stripe = get_stripe_sync()
    new_price_id = cfg.plan.STRIPE_PRICE_IDS.get(new_plan)
    if new_plan != PlanConfig.FREE and not new_price_id:
        raise ValueError(f"Invalid plan: {new_plan}")

    subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)
    if subscription.get("customer") != user.stripe_customer_id:
        raise ValueError("Subscription customer mismatch")
    if subscription.get("status") not in ("active", "trialing"):
        raise ValueError("Subscription is not active")
    if subscription.get("schedule"):
        raise ValueError("A plan change is already scheduled")
    if new_plan == PlanConfig.FREE:
        stripe.Subscription.modify(user.stripe_subscription_id, cancel_at_period_end=True)
        return True
    if subscription.get("cancel_at_period_end"):
        raise ValueError("Subscription is scheduled for cancellation")
    items = subscription.get("items", {}).get("data", [])
    if len(items) != 1:
        raise ValueError("Expected one subscription item")
    item = items[0]
    start = subscription.get("current_period_start") or item.get("current_period_start")
    end = subscription.get("current_period_end") or item.get("current_period_end")
    if not start or not end:
        raise ValueError("Subscription period is missing")
    schedule = stripe.SubscriptionSchedule.create(from_subscription=user.stripe_subscription_id)
    try:
        stripe.SubscriptionSchedule.modify(
            schedule["id"],
            end_behavior="release",
            proration_behavior="none",
            phases=[
                {"start_date": start, "end_date": end,
                 "items": [{"price": item["price"]["id"], "quantity": item.get("quantity", 1)}],
                 "proration_behavior": "none"},
                {"start_date": end, "iterations": 1,
                 "items": [{"price": new_price_id, "quantity": item.get("quantity", 1)}],
                 "proration_behavior": "none"},
            ],
        )
    except Exception:
        stripe.SubscriptionSchedule.release(schedule["id"])
        raise

    return True


def is_trial_active(user: User) -> bool:
    """Check if user is in free trial period."""
    if user.plan != PlanConfig.FREE:
        return False
    if user.trial_ends_at and user.trial_ends_at > datetime.utcnow():
        return True
    return False


def get_effective_plan(user: User) -> str:
    """Get effective plan (trial users get PRO features)."""
    if is_trial_active(user):
        return PlanConfig.PRO
    return user.plan


def handle_webhook_event(event: dict):
    """Process Stripe webhook event and update user record."""
    from database.engine import get_session
    event_type = event["type"]
    data = event["data"]["object"]

    with get_session() as session:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(session, data)
        elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
            _handle_subscription_updated(session, data)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_canceled(session, data)
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(session, data)
        session.commit()


def _handle_checkout_completed(session, session_obj):
    user_id = session_obj.get("metadata", {}).get("user_id")
    if user_id:
        user = session.query(User).filter(User.id == int(user_id)).first()
        if user:
            user.stripe_subscription_id = session_obj.get("subscription")


def _handle_subscription_updated(session, sub):
    customer_id = sub.get("customer")
    user = session.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    cfg = _get_config()
    user.stripe_subscription_id = sub.get("id")
    user.subscription_status = sub.get("status")
    user.current_period_end = datetime.fromtimestamp(sub.get("current_period_end"))

    items = sub.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        previous_plan = user.plan
        new_plan = None
        for plan, pid in cfg.plan.STRIPE_PRICE_IDS.items():
            if pid == price_id:
                new_plan = plan
                break
        if new_plan and new_plan != previous_plan:
            # Trim prefectures while user.plan still holds the old plan's limit.
            adjust_prefectures_for_plan_change(user, new_plan)
            user.plan = new_plan


def _handle_subscription_canceled(session, sub):
    customer_id = sub.get("customer")
    user = session.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        user.plan = PlanConfig.FREE
        user.subscription_status = "canceled"
        user.stripe_subscription_id = None
        user.current_period_end = None
        user.allowed_prefectures = None  # Reset prefectures on cancellation


def _handle_payment_failed(session, invoice):
    customer_id = invoice.get("customer")
    user = session.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        user.subscription_status = "past_due"