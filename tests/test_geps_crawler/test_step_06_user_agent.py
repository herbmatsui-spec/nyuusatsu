from crawler.utils.user_agent import get_random_user_agent, USER_AGENTS

def test_user_agent_returns_string():
    """UA文字列が返されるか"""
    ua = get_random_user_agent()
    assert isinstance(ua, str)
    assert len(ua) > 20

def test_user_agent_from_list():
    """返されるUAがリスト内のものか"""
    ua = get_random_user_agent()
    assert ua in USER_AGENTS

def test_user_agent_list_not_empty():
    """UAリストが空でないこと"""
    assert len(USER_AGENTS) >= 3

def test_user_agent_list_contains_chrome():
    """Chrome UAが含まれること"""
    has_chrome = any("Chrome" in ua for ua in USER_AGENTS)
    assert has_chrome

def test_user_agent_multiple_calls():
    """複数回呼び出しても常にリスト内の値を返す"""
    for _ in range(50):
        ua = get_random_user_agent()
        assert ua in USER_AGENTS
