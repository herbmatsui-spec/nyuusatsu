from __future__ import annotations

from functools import wraps
from typing import Callable, Optional

import streamlit as st

from services.auth_service import AuthService


def require_permission(action: str, resource: str):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            token = st.session_state.get("auth_token")
            session = kwargs.get("db") or (next(st.session_state.get("db_session_gen")) if "db_session_gen" in st.session_state else None)
            if not token or not session:
                st.error("ログインが必要です。")
                st.stop()
            auth = AuthService(session)
            user = auth.get_current_user(token)
            if not user or not auth.has_permission(user, action, resource):
                st.error("権限がありません。")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator
