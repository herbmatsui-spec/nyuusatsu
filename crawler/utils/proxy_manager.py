import os
from typing import Optional, List

class ProxyManager:
    def __init__(self, proxies: Optional[List[str]] = None):
        """
        プロキシのローテーションを管理するクラス。
        proxies が指定されない場合は、環境変数 PROXY_LIST から読み込む（カンマ区切り）。
        """
        self.proxies = proxies or []
        if not self.proxies:
            env_proxies = os.getenv("PROXY_LIST", "")
            if env_proxies:
                self.proxies = [p.strip() for p in env_proxies.split(",") if p.strip()]
        
        self.current_index = 0

    def get_next_proxy(self) -> Optional[str]:
        """
        次のプロキシURLを返す（プロキシが未設定の場合は None を返す）
        """
        if not self.proxies:
            return None
        
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return proxy

    def get_playwright_proxy_dict(self) -> Optional[dict]:
        """
        Playwrightのブラウザコンテキスト起動用のプロキシ辞書を生成して返す
        """
        proxy_url = self.get_next_proxy()
        if not proxy_url:
            return None
        
        # e.g. http://username:password@ip:port または http://ip:port
        return {"server": proxy_url}
