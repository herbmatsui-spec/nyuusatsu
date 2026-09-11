"""Stripe client utilities."""
import os
import stripe
from config_dir import AppConfig


_config = AppConfig()


def get_stripe_client() -> stripe.StripeClient:
    """Return async Stripe client (for FastAPI)."""
    return stripe.StripeClient(_config.stripe.secret_key)


def get_stripe_sync():
    """Return synchronous Stripe module (for Flask/Streamlit)."""
    stripe.api_key = _config.stripe.secret_key
    return stripe