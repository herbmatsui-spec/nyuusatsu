"""Tests for User Agent utility."""

import pytest
from unittest.mock import patch
from crawler.utils.user_agent import (
    USER_AGENTS,
    get_random_user_agent,
)


class TestUserAgent:
    """user_agent のテスト。"""

    def test_user_agents_list(self):
        """USER_AGENTS リストの確認"""
        assert len(USER_AGENTS) == 5
        for ua in USER_AGENTS:
            assert isinstance(ua, str)
            assert len(ua) > 0
            assert "Mozilla" in ua

    def test_get_random_user_agent(self):
        """ランダムUser-Agent取得"""
        ua = get_random_user_agent()
        
        assert isinstance(ua, str)
        assert ua in USER_AGENTS
        assert "Mozilla" in ua

    def test_multiple_calls_return_different(self):
        """複数回呼び出すと異なる値が返る可能性がある"""
        # 統計的に全く同じ値が5回連続で返ることは極めて稀
        results = [get_random_user_agent() for _ in range(10)]
        
        # すべて USER_AGENTS に含まれる
        for r in results:
            assert r in USER_AGENTS
        
        # 少なくとも2種類以上返ることを期待（確率的テスト）
        # 全く同じ値が10回続く確率は (1/5)^9 ≈ 5e-7
        unique = set(results)
        assert len(unique) >= 2

    def test_all_agents_valid_format(self):
        """すべてのエージェントが有効な形式"""
        for ua in USER_AGENTS:
            # 基本的なUser-Agent文字列の要素を含む
            assert "Mozilla" in ua
            # ブラウザ名のいずれかを含む
            assert any(browser in ua for browser in ["Chrome", "Firefox", "Safari", "Edg"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])