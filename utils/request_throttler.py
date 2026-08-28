"""利用者ごとのリクエスト抑制（固定窓・インメモリ）

API プロバイダー側のレートリミット（utils/rate_limiter.py の Token Bucket）とは
別に、Web アプリの悪用を防ぐための「同じクライアントからの過剰なアップロード」
を抑止する。
"""
import threading
import time
from collections import defaultdict
from typing import Dict, Tuple


class RequestThrottler:
    """固定時間窓でリクエスト数を制限する。"""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str = "default") -> bool:
        with self._lock:
            now = time.time()
            window = self._hits[key]
            # 古いヒットを除去
            cutoff = now - self.window_seconds
            while window and window[0] < cutoff:
                window.pop(0)
            if len(window) >= self.max_requests:
                return False
            window.append(now)
            return True

    def get_remaining(self, key: str = "default") -> int:
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            window = self._hits[key]
            while window and window[0] < cutoff:
                window.pop(0)
            return max(0, self.max_requests - len(window))

    def get_reset_in_seconds(self, key: str = "default") -> int:
        with self._lock:
            window = self._hits.get(key)
            if not window:
                return 0
            return max(0, int(self.window_seconds - (time.time() - window[0])))


_throttler: Dict[Tuple[int, int], "RequestThrottler"] = {}
_throttler_lock = threading.Lock()


def get_request_throttler(max_requests: int = 10, window_seconds: int = 60) -> RequestThrottler:
    key = (max_requests, window_seconds)
    with _throttler_lock:
        if key not in _throttler:
            _throttler[key] = RequestThrottler(max_requests, window_seconds)
    return _throttler[key]
