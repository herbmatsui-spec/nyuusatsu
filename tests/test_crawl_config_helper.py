import pytest
from config import CrawlerConfig
from crawler.utils.crawl_config_helper import get_crawl_config_for_agency, get_all_crawl_targets, CrawlTarget
from config.award_urls import AWARD_URL_PATTERNS

def test_get_crawl_config_for_agency_success():
    \"\"\"定義済みの機関で正しい CrawlTarget が生成されるかテスト\"\"\"
    base_config = CrawlerConfig()
    agency_key = \"tokyo\"
    
    target = get_crawl_config_for_agency(agency_key, base_config)
    
    assert target is not None
    assert isinstance(target, CrawlTarget)
    assert target.agency_key == agency_key
    assert target.name == AWARD_URL_PATTERNS[\"tokyo\"][\"name\"]
    assert target.list_url == AWARD_URL_PATTERNS[\"tokyo\"][\"list_url\"]
    assert target.user_agent == base_config.user_agent
    assert target.timeout == base_config.request_timeout

def test_get_crawl_crawl_config_for_agency_not_found():
    \"\"\"未定義の機関で None が返るかテスト\"\"\"
    base_config = CrawlerConfig()
    target = get_crawl_config_for_agency(\"non_existent_agency\", base_config)
    assert target is None

def test_get_all_crawl_targets():
    \"\"\"すべてのターゲットが正しく抽出されるかテスト\"\"\"
    base_config = CrawlerConfig()
    targets = get_all_crawl_targets(base_config)
    
    assert isinstance(targets, dict)
    assert len(targets) == len(AWARD_URL_PATTERNS)
    for key in AWARD_URL_PATTERNS.keys():
        assert key in targets
        assert targets[key].agency_key == key

if __name__ == \"__main__\":
    pytest.main([__file__])
