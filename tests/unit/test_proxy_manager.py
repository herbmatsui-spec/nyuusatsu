"""Tests for Proxy Manager utility."""

import pytest
import os
from unittest.mock import patch
from crawler.utils.proxy_manager import ProxyManager


class TestProxyManager:
    """ProxyManager のテスト。"""

    def test_init_empty(self):
        """空で初期化"""
        pm = ProxyManager()
        assert pm.proxies == []
        assert pm.current_index == 0

    def test_init_with_proxies(self):
        """プロキシリストで初期化"""
        proxies = ["http://proxy1:8080", "http://proxy2:8080"]
        pm = ProxyManager(proxies=proxies)
        assert pm.proxies == proxies
        assert pm.current_index == 0

    def test_init_empty_list(self):
        """空リストで初期化"""
        pm = ProxyManager(proxies=[])
        assert pm.proxies == []
        assert pm.get_next_proxy() is None

    @patch.dict(os.environ, {"PROXY_LIST": "http://env1:8080,http://env2:8080"})
    def test_init_from_env(self):
        """環境変数から読み込み"""
        pm = ProxyManager()
        assert len(pm.proxies) == 2
        assert pm.proxies[0] == "http://env1:8080"
        assert pm.proxies[1] == "http://env2:8080"

    @patch.dict(os.environ, {"PROXY_LIST": "  http://env1:8080 ,  http://env2:8080  "})
    def test_init_from_env_with_spaces(self):
        """環境変数の空白を除去"""
        pm = ProxyManager()
        assert pm.proxies[0] == "http://env1:8080"
        assert pm.proxies[1] == "http://env2:8080"

    @patch.dict(os.environ, {"PROXY_LIST": ""})
    def test_init_empty_env(self):
        """空の環境変数"""
        pm = ProxyManager()
        assert pm.proxies == []

    @patch.dict(os.environ, {"PROXY_LIST": "http://env1:8080,,http://env2:8080"})
    def test_init_env_empty_entries(self):
        """環境変数に空エントリがある場合"""
        pm = ProxyManager()
        assert len(pm.proxies) == 2

    def test_get_next_proxy_empty(self):
        """プロキシなしの場合 None"""
        pm = ProxyManager()
        assert pm.get_next_proxy() is None

    def test_get_next_proxy_single(self):
        """単一プロキシのローテーション"""
        pm = ProxyManager(proxies=["http://proxy:8080"])
        assert pm.get_next_proxy() == "http://proxy:8080"
        assert pm.get_next_proxy() == "http://proxy:8080"

    def test_get_next_proxy_multiple(self):
        """複数プロキシのローテーション"""
        proxies = ["http://proxy1:8080", "http://proxy2:8080", "http://proxy3:8080"]
        pm = ProxyManager(proxies=proxies)
        
        assert pm.get_next_proxy() == "http://proxy1:8080"
        assert pm.get_next_proxy() == "http://proxy2:8080"
        assert pm.get_next_proxy() == "http://proxy3:8080"
        assert pm.get_next_proxy() == "http://proxy1:8080"  # ループ

    def test_get_playwright_proxy_dict_none(self):
        """プロキシなしの場合 None"""
        pm = ProxyManager()
        assert pm.get_playwright_proxy_dict() is None

    def test_get_playwright_proxy_dict_with_proxy(self):
        """プロキシがある場合 dict を返す"""
        pm = ProxyManager(proxies=["http://user:pass@proxy:8080"])
        result = pm.get_playwright_proxy_dict()
        assert result == {"server": "http://user:pass@proxy:8080"}

    def test_get_playwright_proxy_dict_rotation(self):
        """Playwright用もローテーションする"""
        pm = ProxyManager(proxies=["http://proxy1:8080", "http://proxy2:8080"])
        
        assert pm.get_playwright_proxy_dict() == {"server": "http://proxy1:8080"}
        assert pm.get_playwright_proxy_dict() == {"server": "http://proxy2:8080"}
        assert pm.get_playwright_proxy_dict() == {"server": "http://proxy1:8080"}

    def test_explicit_proxies_override_env(self):
        """明示的なプロキシは環境変数を上書き"""
        with patch.dict(os.environ, {"PROXY_LIST": "http://env:8080"}):
            pm = ProxyManager(proxies=["http://explicit:8080"])
            assert pm.proxies == ["http://explicit:8080"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])