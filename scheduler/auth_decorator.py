"""認証デコレータ - スケジューラ管理APIの保護 (Step 44)。"""

import functools
import os
from typing import Callable, Optional
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

# 環境変数からAPIキーを取得
SCHEDULER_API_KEY = os.getenv("SCHEDULER_API_KEY")
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"


def require_scheduler_auth(
    func: Optional[Callable] = None,
    *,
    required_roles: Optional[list[str]] = None,
) -> Callable:
    """
    スケジューラ管理エンドポイントへのアクセスを制限するデコレータ。
    
    使用例:
        @router.post("/scheduler/start")
        @require_scheduler_auth
        async def start_scheduler(request: Request):
            ...
    """
    if not ENABLE_AUTH:
        return func if func else (lambda f: f)
    
    if func is None:
        return lambda f: require_scheduler_auth(f, required_roles=required_roles)
    
    @functools.wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # APIキー認証
        credentials: HTTPAuthorizationCredentials = await security(request)
        
        if not credentials:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Provide API key via Authorization header."
            )
        
        if credentials.credentials != SCHEDULER_API_KEY:
            raise HTTPException(
                status_code=403,
                detail="Invalid API key."
            )
        
        # ロールベースアクセス制御（将来拡張用）
        if required_roles:
            user_role = request.headers.get("X-User-Role", "viewer")
            if user_role not in required_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Required role: {required_roles}. Current: {user_role}"
                )
        
        return await func(request, *args, **kwargs)
    
    return wrapper


def get_current_user(request: Request) -> dict:
    """現在のユーザー情報を取得（認証必須モード時）。"""
    if not ENABLE_AUTH:
        return {"role": "admin", "authenticated": False}
    
    credentials: HTTPAuthorizationCredentials = security(request)
    if not credentials or credentials.credentials != SCHEDULER_API_KEY:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    return {
        "role": request.headers.get("X-User-Role", "admin"),
        "authenticated": True,
    }


# 後方互換性のための同期版
def sync_require_scheduler_auth(func: Callable) -> Callable:
    """同期関数用の認証デコレータ（レガシー対応）。"""
    if not ENABLE_AUTH:
        return func
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 簡易的なAPIキーチェック（実際のリクエストコンテキストがないため制限あり）
        import inspect
        # 同期関数では完全な認証は困難。ログ出力のみ。
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Sync auth check for {func.__name__} - ensure ENABLE_AUTH=false or use async version")
        return func(*args, **kwargs)
    return wrapper