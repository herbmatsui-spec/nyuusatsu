import asyncio
import time
from urllib.parse import urlparse

class RateLimiter:
    def __init__(self, default_delay: float = 3.0):
        """
        ドメインごとのアクセス間隔を制御するクラス。
        """
        self.default_delay = default_delay
        self.last_access_times = {}

    def _get_domain(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    async def throttle(self, url: str, custom_delay: float = None) -> None:
        """
        指定されたURLのドメインに対する前回アクセスからの経過時間を確認し、
        必要であればスリープしてアクセス制限を順守する。
        """
        domain = self._get_domain(url)
        delay = custom_delay if custom_delay is not None else self.default_delay

        last_time = self.last_access_times.get(domain)
        if last_time is not None:
            elapsed = time.time() - last_time
            remaining = delay - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
        
        # アクセス時刻を更新
        self.last_access_times[domain] = time.time()
