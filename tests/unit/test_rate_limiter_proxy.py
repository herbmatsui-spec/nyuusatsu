import pytest
import time
from unittest.mock import Mock, patch

from crawler.utils.rate_limiter import RateLimiter
from crawler.utils.proxy_manager import ProxyManager


class TestRateLimiter:
    """Test cases for RateLimiter class."""

    def test_initialization_with_default_delay(self):
        """Test RateLimiter initialization with default delay."""
        limiter = RateLimiter()
        assert limiter.default_delay == 3.0
        assert limiter.last_access_times == {}

    def test_initialization_with_custom_delay(self):
        """Test RateLimiter initialization with custom delay."""
        limiter = RateLimiter(default_delay=5.0)
        assert limiter.default_delay == 5.0

    def test_get_domain(self):
        """Test domain extraction from URL."""
        limiter = RateLimiter()
        assert limiter._get_domain("https://www.example.com/path") == "www.example.com"
        assert limiter._get_domain("http://api.example.org/api/v1") == "api.example.org"
        assert limiter._get_domain("https://localhost:8080/test") == "localhost:8080"
        assert limiter._get_domain("invalid-url") == "unknown"

    def test_throttle_sync_first_access(self):
        """Test first access doesn't wait."""
        limiter = RateLimiter(default_delay=1.0)
        start = time.time()
        limiter.throttle_sync("https://example.com/page1")
        elapsed = time.time() - start
        assert elapsed < 0.1  # Should not wait on first access

    def test_throttle_sync_waits_on_repeat(self):
        """Test throttle_sync waits on repeated access to same domain."""
        limiter = RateLimiter(default_delay=0.1)
        
        # First access
        limiter.throttle_sync("https://example.com/page1")
        
        # Second access should wait
        start = time.time()
        limiter.throttle_sync("https://example.com/page2")
        elapsed = time.time() - start
        assert elapsed >= 0.09  # Should wait approximately 0.1 seconds

    def test_throttle_sync_custom_delay(self):
        """Test throttle_sync with custom delay."""
        limiter = RateLimiter(default_delay=1.0)
        limiter.throttle_sync("https://example.com/page1")
        
        # Use custom shorter delay
        start = time.time()
        limiter.throttle_sync("https://example.com/page2", custom_delay=0.05)
        elapsed = time.time() - start
        assert elapsed >= 0.04

    def test_different_domains_independent(self):
        """Test different domains have independent rate limits."""
        limiter = RateLimiter(default_delay=0.1)
        
        limiter.throttle_sync("https://example.com/page1")
        limiter.throttle_sync("https://other.com/page1")
        
        # Second access to example.com should wait
        start = time.time()
        limiter.throttle_sync("https://example.com/page2")
        elapsed = time.time() - start
        assert elapsed >= 0.09
        
        # But other.com should not wait
        start = time.time()
        limiter.throttle_sync("https://other.com/page2")
        elapsed = time.time() - start
        assert elapsed < 0.05

    @pytest.mark.asyncio
    async def test_throttle_async_first_access(self):
        """Test async throttle doesn't wait on first access."""
        limiter = RateLimiter(default_delay=1.0)
        start = time.time()
        await limiter.throttle("https://example.com/page1")
        elapsed = time.time() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_throttle_async_waits_on_repeat(self):
        """Test async throttle waits on repeated access."""
        limiter = RateLimiter(default_delay=0.1)
        
        await limiter.throttle("https://example.com/page1")
        
        start = time.time()
        await limiter.throttle("https://example.com/page2")
        elapsed = time.time() - start
        assert elapsed >= 0.09

    @pytest.mark.asyncio
    async def test_async_custom_delay(self):
        """Test async throttle with custom delay."""
        limiter = RateLimiter(default_delay=1.0)
        await limiter.throttle("https://example.com/page1")
        
        start = time.time()
        await limiter.throttle("https://example.com/page2", custom_delay=0.05)
        elapsed = time.time() - start
        assert elapsed >= 0.04

    def test_throttle_sync_updates_access_time(self):
        """Test that throttle_sync updates last access time."""
        limiter = RateLimiter(default_delay=0.1)
        
        limiter.throttle_sync("https://example.com/page1")
        assert "example.com" in limiter.last_access_times
        
        # Wait a bit and access again
        time.sleep(0.15)
        limiter.throttle_sync("https://example.com/page2")
        
        # Should have updated the time
        assert limiter.last_access_times["example.com"] is not None


class TestProxyManager:
    """Test cases for ProxyManager class."""

    def test_initialization_with_empty_list(self):
        """Test ProxyManager initialization with empty list."""
        manager = ProxyManager(proxies=[])
        assert manager.proxies == []
        assert manager.current_index == 0

    def test_initialization_with_proxies(self):
        """Test ProxyManager initialization with proxy list."""
        proxies = ["http://proxy1:8080", "http://proxy2:8080"]
        manager = ProxyManager(proxies=proxies)
        assert manager.proxies == proxies
        assert manager.current_index == 0

    def test_get_next_proxy_empty(self):
        """Test get_next_proxy returns None for empty list."""
        manager = ProxyManager(proxies=[])
        assert manager.get_next_proxy() is None

    def test_get_next_proxy_rotation(self):
        """Test proxy rotation."""
        proxies = ["http://proxy1:8080", "http://proxy2:8080", "http://proxy3:8080"]
        manager = ProxyManager(proxies=proxies)
        
        assert manager.get_next_proxy() == "http://proxy1:8080"
        assert manager.get_next_proxy() == "http://proxy2:8080"
        assert manager.get_next_proxy() == "http://proxy3:8080"
        assert manager.get_next_proxy() == "http://proxy1:8080"  # Wraps around

    def test_get_next_proxy_single(self):
        """Test single proxy rotation."""
        manager = ProxyManager(proxies=["http://proxy1:8080"])
        
        assert manager.get_next_proxy() == "http://proxy1:8080"
        assert manager.get_next_proxy() == "http://proxy1:8080"
        assert manager.current_index == 0  # Stays at 0 for single proxy

    def test_initialization_from_env(self):
        """Test initialization from environment variable."""
        with patch.dict('os.environ', {'PROXY_LIST': 'http://env1:8080, http://env2:8080'}):
            manager = ProxyManager(proxies=None)
            assert len(manager.proxies) == 2
            assert manager.proxies[0] == "http://env1:8080"
            assert manager.proxies[1] == "http://env2:8080"

    def test_initialization_from_env_with_spaces(self):
        """Test initialization from env with extra spaces."""
        with patch.dict('os.environ', {'PROXY_LIST': '  http://a:8080 ,  http://b:8080  ,'}):
            manager = ProxyManager(proxies=None)
            assert len(manager.proxies) == 2
            assert manager.proxies[0] == "http://a:8080"
            assert manager.proxies[1] == "http://b:8080"

    def test_get_playwright_proxy_dict(self):
        """Test get_playwright_proxy_dict."""
        manager = ProxyManager(proxies=["http://proxy:8080"])
        proxy_dict = manager.get_playwright_proxy_dict()
        assert proxy_dict == {"server": "http://proxy:8080"}

    def test_get_playwright_proxy_dict_empty(self):
        """Test get_playwright_proxy_dict with no proxies."""
        manager = ProxyManager(proxies=[])
        assert manager.get_playwright_proxy_dict() is None

    def test_get_next_proxy_after_env_init(self):
        """Test proxy rotation after env initialization."""
        with patch.dict('os.environ', {'PROXY_LIST': 'http://p1:8080,http://p2:8080'}):
            manager = ProxyManager()
            assert manager.get_next_proxy() == "http://p1:8080"
            assert manager.get_next_proxy() == "http://p2:8080"
            assert manager.get_next_proxy() == "http://p1:8080"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])