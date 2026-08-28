from crawler.utils.proxy_manager import ProxyManager

def test_proxy_manager_empty():
    """プロキシ未設定時はNoneを返す"""
    pm = ProxyManager(proxies=[])
    assert pm.get_next_proxy() is None

def test_proxy_manager_with_proxies():
    """プロキシが設定されている場合、最初のプロキシを返す"""
    pm = ProxyManager(proxies=["http://p1:8080", "http://p2:8080"])
    assert pm.get_next_proxy() == "http://p1:8080"

def test_proxy_manager_rotation():
    """プロキシがローテーションされるか"""
    pm = ProxyManager(proxies=["http://p1:8080", "http://p2:8080", "http://p3:8080"])
    assert pm.get_next_proxy() == "http://p1:8080"
    assert pm.get_next_proxy() == "http://p2:8080"
    assert pm.get_next_proxy() == "http://p3:8080"
    assert pm.get_next_proxy() == "http://p1:8080"  # ループ

def test_proxy_manager_single_proxy():
    """プロキシが1つだけの場合"""
    pm = ProxyManager(proxies=["http://only:8080"])
    assert pm.get_next_proxy() == "http://only:8080"
    assert pm.get_next_proxy() == "http://only:8080"

def test_proxy_manager_playwright_dict():
    """Playwright用プロキシ辞書が正しいか"""
    pm = ProxyManager(proxies=["http://proxy:8080"])
    result = pm.get_playwright_proxy_dict()
    assert result == {"server": "http://proxy:8080"}

def test_proxy_manager_playwright_dict_none():
    """プロキシ未設定時はNoneを返す"""
    pm = ProxyManager(proxies=[])
    assert pm.get_playwright_proxy_dict() is None

def test_proxy_manager_from_env(monkeypatch):
    """環境変数からプロキシリストを読み込めるか"""
    monkeypatch.setenv("PROXY_LIST", "http://env1:8080, http://env2:8080")
    pm = ProxyManager()
    assert pm.get_next_proxy() == "http://env1:8080"
    assert pm.get_next_proxy() == "http://env2:8080"
