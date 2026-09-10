"""API usage tracking and limits."""
from datetime import datetime
from typing import Optional

from database.engine import get_session
from database.models.api_usage import ApiUsage
from utils.auth_decorator import get_current_user
from utils.plan_gate import get_user_limits


def check_api_limit() -> bool:
    """Check if current user has exceeded monthly API limit."""
    user = get_current_user()
    if not user:
        return False

    limits = get_user_limits(user)
    monthly_limit = limits.get("api_requests_monthly")
    if monthly_limit is None or monthly_limit <= 0:
        return False  # not allowed or unlimited handled elsewhere

    with get_session() as session:
        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = session.query(ApiUsage).filter(
            ApiUsage.user_id == user.id,
            ApiUsage.month == current_month
        ).first()
        count = usage.count if usage else 0
        return count < monthly_limit


def increment_api_usage() -> int:
    """Increment API usage counter for current user. Returns new count."""
    user = get_current_user()
    if not user:
        return 0

    with get_session() as session:
        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = session.query(ApiUsage).filter(
            ApiUsage.user_id == user.id,
            ApiUsage.month == current_month
        ).first()
        if usage:
            usage.count += 1
            new_count = usage.count
        else:
            usage = ApiUsage(user_id=user.id, month=current_month, count=1)
            session.add(usage)
            new_count = 1
        session.commit()
        return new_count


def get_api_usage() -> dict:
    """Get current user's API usage stats."""
    user = get_current_user()
    if not user:
        return {"count": 0, "limit": 0, "remaining": 0}

    limits = get_user_limits(user)
    monthly_limit = limits.get("api_requests_monthly", 0)

    with get_session() as session:
        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = session.query(ApiUsage).filter(
            ApiUsage.user_id == user.id,
            ApiUsage.month == current_month
        ).first()
        count = usage.count if usage else 0

    return {
        "count": count,
        "limit": monthly_limit,
        "remaining": max(0, monthly_limit - count) if monthly_limit > 0 else -1,
    }


def reset_api_usage(user_id: int) -> None:
    """Reset API usage for a user (admin function)."""
    with get_session() as session:
        session.query(ApiUsage).filter(ApiUsage.user_id == user_id).delete()
        session.commit()