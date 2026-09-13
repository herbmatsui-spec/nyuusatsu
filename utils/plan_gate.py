"""Plan gate middleware - enforce plan limits on features."""
from functools import wraps
from typing import Callable, Optional, List

import streamlit as st

from utils.auth_decorator import get_current_user
from services.billing_service import get_effective_plan
from config import PlanConfig


def require_plan(*allowed_plans: str):
    """Decorator to restrict feature access by plan."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                st.error("ログインが必要です")
                st.stop()

            effective = get_effective_plan(user)
            if effective not in allowed_plans:
                plan_names = {
                    PlanConfig.FREE: "無料",
                    PlanConfig.STANDARD: "スタンダード",
                    PlanConfig.PRO: "プロ",
                    PlanConfig.ENTERPRISE: "エンタープライズ",
                }
                allowed_names = [plan_names.get(p, p) for p in allowed_plans]
                st.error(f"この機能は {' / '.join(allowed_names)} プラン以上で利用できます")
                st.info("👉 [プラン・請求ページ](app_billing.py) からアップグレードしてください")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_feature(feature: str):
    """Decorator to check if user's plan includes a specific feature."""
    feature_limits = {
        "search_unlimited": [PlanConfig.STANDARD, PlanConfig.PRO, PlanConfig.ENTERPRISE],
        "search_days": [PlanConfig.FREE, PlanConfig.STANDARD, PlanConfig.PRO, PlanConfig.ENTERPRISE],
        "pdf_extract": [PlanConfig.FREE, PlanConfig.STANDARD, PlanConfig.PRO, PlanConfig.ENTERPRISE],
        "pdf_extract_unlimited": [PlanConfig.STANDARD, PlanConfig.PRO, PlanConfig.ENTERPRISE],
        "export": [PlanConfig.STANDARD, PlanConfig.PRO, PlanConfig.ENTERPRISE],
        "api_access": [PlanConfig.STANDARD, PlanConfig.PRO, PlanConfig.ENTERPRISE],
    }

    allowed = feature_limits.get(feature, [PlanConfig.ENTERPRISE])
    return require_plan(*allowed)


def get_user_limits(user) -> dict:
    """Get effective limits for current user."""
    effective = get_effective_plan(user)
    return PlanConfig.LIMITS.get(effective, PlanConfig.LIMITS[PlanConfig.FREE])


def check_daily_limit(user, feature: str, current_count: int) -> bool:
    """Check if user has exceeded daily limit for feature."""
    limits = get_user_limits(user)
    limit_key = f"{feature}_daily"
    daily_limit = limits.get(limit_key)
    if daily_limit is None:
        return True  # unlimited
    return current_count < daily_limit


def check_monthly_limit(user, feature: str, current_count: int) -> bool:
    """Check if user has exceeded monthly limit for feature."""
    limits = get_user_limits(user)
    limit_key = f"{feature}_monthly"
    monthly_limit = limits.get(limit_key)
    if monthly_limit is None:
        return True  # unlimited
    return current_count < monthly_limit