"""Tests for Rate Limiter utility."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from crawler.utils.rate_limiter import RateLimiter


class TestRateLimiter:
    """RateLimiter のテスト。"""

    @pytest.fixture
    def rate_limiter(self):
        """デフォルト遅延 3.0 秒の RateLimiter"""
        return RateLimiter(default_delay=3.0)

    @pytest.fixture
    def rate_limiter_custom(self):
        """カスタム遅延 1.0 秒の RateLimiter"""
        return RateLimiter(default_delay=1.0)

    def test_init_default(self):
        """デフォルト値で初期化される"""
        rl = RateLimiter()
        assert rl.default_delay == 3.0
        assert rl.last_access_times == {}

    def test_init_custom_delay(self):
        """カスタム遅延で初期化される"""
        rl = RateLimiter(default_delay=5.0)
        assert rl.default_delay == 5.0

    def test_get_domain(self):
        """ドメイン抽出"""
        rl = RateLimiter()
        assert rl._get_domain("https://example.com/path") == "example.com"
        assert rl._get_domain("http://sub.example.com:8080/path") == "sub.example.com:8080"
        assert rl._get_domain("https://example.com") == "example.com"
        assert rl._get_domain("invalid") == "unknown"

    @pytest.mark.asyncio
    async def test_throttle_first_access(self, rate_limiter):
        """初回アクセスはスリープしない"""
        url = "https://example.com"
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await rate_limiter.throttle(url)
            mock_sleep.assert_not_called()
            assert "example.com" in rate_limiter.last_access_times

    @pytest.mark.asyncio
    async def test_throttle_within_delay(self, rate_limiter):
        """遅延内での再アクセスはスリープする"""
        url = "https://example.com"
        
        # 初回アクセス
        await rate_limiter.throttle(url)
        first_time = rate_limiter.last_access_times["example.com"]
        
        # 0.1秒後に再アクセス
        with patch("time.time", return_value=first_time + 0.1):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await rate_limiter.throttle(url)
                mock_sleep.assert_called_once()
                call_args = mock_sleep.call_args[0][0]
                # 3.0 - 0.1 = 2.9 秒程度スリープ
                assert 2.8 <= call_args <= 3.0

    @pytest.mark.asyncio
    async def test_throttle_after_delay(self, rate_limiter):
        """遅延経過後の再アクセスはスリープしない"""
        url = "https://example.com"
        
        await rate_limiter.throttle(url)
        first_time = rate_limiter.last_access_times["example.com"]
        
        # 4.0秒後に再アクセス（デフォルト遅延 3.0 を超える）
        with patch("time.time", return_value=first_time + 4.0):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await rate_limiter.throttle(url)
                mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_throttle_custom_delay(self, rate_limiter):
        """カスタム遅延が適用される"""
        url = "https://example.com"
        
        await rate_limiter.throttle(url)
        first_time = rate_limiter.last_access_times["example.com"]
        
        # カスタム遅延 1.0 秒、0.5秒後
        with patch("time.time", return_value=first_time + 0.5):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await rate_limiter.throttle(url, custom_delay=1.0)
                mock_sleep.assert_called_once()
                call_args = mock_sleep.call_args[0][0]
                assert 0.4 <= call_args <= 0.6

    def test_throttle_sync_first_access(self, rate_limiter):
        """同期版: 初回アクセスはスリープしない"""
        url = "https://example.com"
        with patch("time.sleep") as mock_sleep:
            rate_limiter.throttle_sync(url)
            mock_sleep.assert_not_called()

    def test_throttle_sync_within_delay(self, rate_limiter):
        """同期版: 遅延内での再アクセスはスリープする"""
        url = "https://example.com"
        
        rate_limiter.throttle_sync(url)
        first_time = rate_limiter.last_access_times["example.com"]
        
        with patch("time.time", return_value=first_time + 0.1):
            with patch("time.sleep") as mock_sleep:
                rate_limiter.throttle_sync(url)
                mock_sleep.assert_called_once()
                call_args = mock_sleep.call_args[0][0]
                assert 2.8 <= call_args <= 3.0

    def test_throttle_sync_after_delay(self, rate_limiter):
        """同期版: 遅延経過後の再アクセスはスリープしない"""
        url = "https://example.com"
        
        rate_limiter.throttle_sync(url)
        first_time = rate_limiter.last_access_times["example.com"]
        
        with patch("time.time", return_value=first_time + 4.0):
            with patch("time.sleep") as mock_sleep:
                rate_limiter.throttle_sync(url)
                mock_sleep.assert_not_called()

    def test_multiple_domains(self, rate_limiter):
        """複数ドメインは独立して管理される"""
        url1 = "https://example.com"
        url2 = "https://other.com"
        
        rate_limiter.throttle_sync(url1)
        rate_limiter.throttle_sync(url2)
        
        assert "example.com" in rate_limiter.last_access_times
        assert "other.com" in rate_limiter.last_access_times
        assert rate_limiter.last_access_times["example.com"] != rate_limiter.last_access_times["other.com"]

    def test_same_domain_different_paths(self, rate_limiter):
        """同一ドメイン・異なるパスは同じドメインとして扱われる"""
        url1 = "https://example.com/path1"
        url2 = "https://example.com/path2"
        
        rate_limiter.throttle_sync(url1)
        first_time = rate_limiter.last_access_times["example.com"]
        
        with patch("time.time", return_value=first_time + 0.1):
            with patch("time.sleep") as mock_sleep:
                rate_limiter.throttle_sync(url2)
                mock_sleep.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])