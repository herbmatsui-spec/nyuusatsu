"""Plan gate middleware - enforce plan limits on features."""
from functools import wraps
from typing import Callable, Optional, List, Set

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
                    PlanConfig.SINGLE_REGION: "シングル地域",
                    PlanConfig.DUAL_REGION: "デュアル地域",
                    PlanConfig.NATIONAL: "全国",
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
        "search_unlimited": [PlanConfig.SINGLE_REGION, PlanConfig.DUAL_REGION, PlanConfig.NATIONAL, PlanConfig.PRO, PlanConfig.ENTERPRISE],
        "search_days": [PlanConfig.FREE, PlanConfig.SINGLE_REGION, PlanConfig.DUAL_REGION, PlanConfig.NATIONAL, PlanConfig.PRO, PlanConfig.ENTERPRISE],
        "pdf_extract": [PlanConfig.FREE, PlanConfig.SINGLE_REGION, PlanConfig.DUAL_REGION, PlanConfig.NATIONAL, PlanConfig.PRO, PlanConfig.ENTERPRISE],
        "pdf_extract_unlimited": [PlanConfig.SINGLE_REGION, PlanConfig.DUAL_REGION, PlanConfig.NATIONAL, PlanConfig.PRO, PlanConfig.ENTERPRISE],
        "export": [PlanConfig.SINGLE_REGION, PlanConfig.DUAL_REGION, PlanConfig.NATIONAL, PlanConfig.PRO, PlanConfig.ENTERPRISE],
        "api_access": [PlanConfig.SINGLE_REGION, PlanConfig.DUAL_REGION, PlanConfig.NATIONAL, PlanConfig.PRO, PlanConfig.ENTERPRISE],
        "prediction": [PlanConfig.PRO, PlanConfig.ENTERPRISE],
    }

    allowed = feature_limits.get(feature, [PlanConfig.ENTERPRISE])
    return require_plan(*allowed)


def get_user_limits(user) -> dict:
    """Get effective limits for current user."""
    effective = get_effective_plan(user)
    return PlanConfig().LIMITS.get(effective, PlanConfig().LIMITS[PlanConfig.FREE])


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


def get_allowed_prefectures(user) -> Set[str]:
    """Get the set of prefecture codes the user is allowed to access."""
    effective = get_effective_plan(user)
    limits = PlanConfig().LIMITS.get(effective, PlanConfig().LIMITS[PlanConfig.FREE])
    max_prefectures = limits.get('prefectures', 1)
    
    # If user has selected prefectures, use those (for single/dual region plans)
    if hasattr(user, 'allowed_prefectures') and user.allowed_prefectures:
        import json
        try:
            selected = set(json.loads(user.allowed_prefectures))
            # For national/pro/enterprise, return all prefectures
            if max_prefectures >= 47:
                return selected if selected else set()  # Will be handled by can_access_prefecture
            return selected
        except (json.JSONDecodeError, TypeError):
            pass
    return set()


def can_access_prefecture(user, target_prefecture: str) -> bool:
    """
    Check if user can access a specific prefecture based on their plan.
    
    Args:
        user: User object
        target_prefecture: Prefecture code (e.g., '13' for Tokyo)
    
    Returns:
        True if access is allowed, False otherwise
    """
    effective = get_effective_plan(user)
    limits = PlanConfig().LIMITS.get(effective, PlanConfig().LIMITS[PlanConfig.FREE])
    max_prefectures = limits.get('prefectures', 1)
    
    # National, Pro, Enterprise - unlimited prefectures
    if max_prefectures >= 47:
        return True
    
    # Get user's selected prefectures
    allowed = get_allowed_prefectures(user)
    
    # If target prefecture is already in allowed list, allow access
    if target_prefecture in allowed:
        return True
    
    # If user hasn't filled their quota yet, allow access (will be added on selection)
    if len(allowed) < max_prefectures:
        return True
    
    # Quota exceeded
    return False


def get_allowed_prefecture_count(user) -> int:
    """Get the maximum number of prefectures allowed for the user's plan."""
    effective = get_effective_plan(user)
    limits = PlanConfig().LIMITS.get(effective, PlanConfig().LIMITS[PlanConfig.FREE])
    return limits.get('prefectures', 1)


def get_current_prefecture_count(user) -> int:
    """Get the current number of prefectures the user has selected."""
    allowed = get_allowed_prefectures(user)
    return len(allowed)


VALID_PREFECTURE_CODES = {f"{i:02d}" for i in range(1, 48)}


def get_search_prefecture_scope(user):
    """Resolve the prefecture scope applied to search queries.

    Returns:
        None: unrestricted (no user, unlimited plan, or trial).
        list[str]: validated prefecture codes the user may access.
        []: restricted plan with no selection - must yield zero results.
    """
    if user is None:
        return None
    effective = get_effective_plan(user)
    limits = PlanConfig().LIMITS.get(effective, PlanConfig().LIMITS[PlanConfig.FREE])
    max_prefectures = limits.get('prefectures', 1)
    if max_prefectures >= 47:
        return None
    if not getattr(user, 'allowed_prefectures', None):
        return []
    import json
    try:
        selected = json.loads(user.allowed_prefectures)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(selected, list):
        return []
    valid = [code for code in selected
             if isinstance(code, str) and code in VALID_PREFECTURE_CODES]
    return valid[:max_prefectures]