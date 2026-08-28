"""セッション管理（プロトタイプ用・インメモリ）

本番環境では Redis 等の共有ストアへ置換することを想定。
Streamlit は同一プロセス内でスクリプトを再実行するため、
モジュールレベルのシングルトンでセッションを保持できる。
"""
import threading
import time
import uuid
from typing import Dict, Optional


class SessionManager:
    def __init__(self, timeout_minutes: int = 60):
        self.timeout_seconds = timeout_minutes * 60
        self._sessions: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def create_session(self, username: str) -> str:
        session_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[session_id] = {
                "username": username,
                "created_at": time.time(),
            }
        return session_id

    def validate_session(self, session_id: str) -> bool:
        if not session_id:
            return False
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            if time.time() - session["created_at"] > self.timeout_seconds:
                del self._sessions[session_id]
                return False
        return True

    def get_username(self, session_id: str) -> Optional[str]:
        if self.validate_session(session_id):
            with self._lock:
                return self._sessions.get(session_id, {}).get("username")
        return None

    def logout(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


_manager: Optional[SessionManager] = None
_manager_lock = threading.Lock()


def get_session_manager(timeout_minutes: int = 60) -> SessionManager:
    """プロセス内シングルトンを取得する。"""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = SessionManager(timeout_minutes=timeout_minutes)
    return _manager
