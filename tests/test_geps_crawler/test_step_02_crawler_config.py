
from geps_crawler import CrawlerConfig
from config_dir import AppConfig

def test_crawler_config_defaults():
    """CrawlerConfigのデフォルト値が正しいか"""
    config = CrawlerConfig()
    assert "geps.go.jp" in config.search_url
    assert config.sleep_interval == 5
    assert config.timeout == 60000
    assert config.temp_dir == "./temp_pdfs"

def test_crawler_config_custom():
    """CrawlerConfigにカスタム値を設定できるか"""
    config = CrawlerConfig(search_url="https://custom.example.com", sleep_interval=10, timeout=30000)
    assert config.search_url == "https://custom.example.com"
    assert config.sleep_interval == 10
    assert config.timeout == 30000

def test_crawler_config_user_agent():
    """User-Agent文字列がChrome互換のものか"""
    config = CrawlerConfig()
    assert "Mozilla" in config.user_agent
    assert "Chrome" in config.user_agent

def test_crawler_config_temp_dir_custom():
    """temp_dirをカスタム設定できるか"""
    config = CrawlerConfig(temp_dir="/tmp/test_pdfs")
    assert config.temp_dir == "/tmp/test_pdfs"

def test_app_config_crawler_defaults():
    """AppConfig内のCrawlerConfigのデフォルト値"""
    config = AppConfig()
    assert config.crawler.temp_dir == "./temp_pdfs"
    assert config.crawler.request_timeout == 30
    assert config.crawler.parallel_downloads == 4

def test_app_config_fallback_defaults():
    """FallbackConfigのデフォルト値"""
    config = AppConfig()
    assert config.fallback.enable_fallback == True
    assert config.fallback.strategy == "try_playwright_first"
    assert config.fallback.retry_on_playwright == 2

def test_app_config_validate_no_error_with_key(monkeypatch):
    """APIキーが設定されている場合、バリデーションエラーが無い"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key_123")
    config = AppConfig()
    errors = config.validate()
    # 少なくともAPIキーが無いというエラーは発生しないはず
    assert not any("API" in e for e in errors)

def test_app_config_validate_bad_strategy():
    """不正なフォールバック戦略でバリデーションエラーが出る"""
    config = AppConfig()
    config.fallback.strategy = "invalid_strategy"
    errors = config.validate()
    assert any("FALLBACK_STRATEGY" in e for e in errors)
