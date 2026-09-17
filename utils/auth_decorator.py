from __future__ import annotations

from datetime import datetime
from functools import wraps
from typing import Callable, Optional

import streamlit as st

from services.auth_service import AuthService
from config import PlanConfig
from services.billing_service import get_effective_plan, is_trial_active
from database.engine import get_session
from database.models.user import User


def is_authenticated() -> bool:
    """Check if user is authenticated and subscription is valid."""
    if not st.session_state.get("authenticated"):
        return False

    # Check subscription validity for paid plans
    user = get_current_user()
    if user and user.plan != PlanConfig.FREE:
        if user.current_period_end and user.current_period_end < datetime.utcnow():
            return False
    return True


def get_current_user() -> Optional[User]:
    """Get current logged-in user from session."""
    if not st.session_state.get("authenticated"):
        return None

    username = st.session_state.get("username")
    if not username:
        return None

    with get_session() as session:
        auth = AuthService(session)
        user = auth.load_user(username)
        if user is None:
            user = session.query(User).filter(User.username == username).first()
        return user


def require_permission(action: str, resource: str):
    """Decorator to require specific permission."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_authenticated():
                st.error("ログインが必要です。")
                st.stop()
            user = get_current_user()
            if not user:
                st.error("ユーザー情報が取得できません。")
                st.stop()

            # For permission checks, we still need a session
            session = kwargs.get("db")
            if session:
                auth = AuthService(session)
                if not auth.has_permission(user, action, resource):
                    st.error("権限がありません。")
                    st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator