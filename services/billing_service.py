"""Billing service - Stripe integration and plan management."""
from datetime import datetime, timezone, timezone
from typing import Optional

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
    stripe = get_stripe_sync()
    customer_id = ensure_stripe_customer(user)
    price_id = cfg.plan.STRIPE_PRICE_IDS.get(plan)
    if not price_id:
        raise ValueError(f"Invalid plan: {plan}")

    trial_days = 7 if user.plan == PlanConfig.FREE else 0

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=cfg.stripe.success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cfg.stripe.cancel_url,
        subscription_data={
            "trial_period_days": trial_days,
            "metadata": {"user_id": str(user.id), "plan": plan}
        },
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
        for plan, pid in cfg.plan.STRIPE_PRICE_IDS.items():
            if pid == price_id:
                user.plan = plan
                break


def _handle_subscription_canceled(session, sub):
    customer_id = sub.get("customer")
    user = session.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        user.plan = PlanConfig.FREE
        user.subscription_status = "canceled"
        user.stripe_subscription_id = None
        user.current_period_end = None


def _handle_payment_failed(session, invoice):
    customer_id = invoice.get("customer")
    user = session.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        user.subscription_status = "past_due"