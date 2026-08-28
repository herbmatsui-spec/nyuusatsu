import pytest
import asyncio
from crawler.utils.rate_limiter import RateLimiter

def test_rate_limiter_init_default():
    """デフォルトの遅延時間が設定されるか"""
    rl = RateLimiter()
    assert rl.default_delay == 3.0
    assert rl.last_access_times == {}

def test_rate_limiter_init_custom():
    """カスタム遅延時間が設定されるか"""
    rl = RateLimiter(default_delay=10.0)
    assert rl.default_delay == 10.0

def test_rate_limiter_get_domain():
    """URLからドメインを正しく抽出するか"""
    rl = RateLimiter()
    assert rl._get_domain("https://www.geps.go.jp/page1") == "www.geps.go.jp"
    assert rl._get_domain("http://example.com:8080/path") == "example.com:8080"

def test_rate_limiter_get_domain_empty():
    """不正なURLのドメイン抽出"""
    rl = RateLimiter()
    assert rl._get_domain("") == "unknown"
    assert rl._get_domain("not-a-url") == "unknown"

@pytest.mark.asyncio
async def test_rate_limiter_first_access_no_delay():
    """初回アクセスは遅延なしで通過するか"""
    rl = RateLimiter(default_delay=5.0)
    start = asyncio.get_event_loop().time()
    await rl.throttle("https://example.com/page1")
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 0.2  # 初回は即座に通過

@pytest.mark.asyncio
async def test_rate_limiter_second_access_delayed():
    """2回目のアクセスで遅延が発生するか"""
    rl = RateLimiter(default_delay=0.2)
    url = "https://example.com/page"
    await rl.throttle(url)
    start = asyncio.get_event_loop().time()
    await rl.throttle(url)
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed >= 0.15  # 0.2秒に近い遅延

@pytest.mark.asyncio
async def test_rate_limiter_different_domains_no_delay():
    """異なるドメインへのアクセスは遅延なし"""
    rl = RateLimiter(default_delay=5.0)
    await rl.throttle("https://a.example.com/page")
    start = asyncio.get_event_loop().time()
    await rl.throttle("https://b.example.com/page")
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 0.2
