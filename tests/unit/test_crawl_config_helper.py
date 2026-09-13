"""Tests for Crawl Config Helper utility."""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

# モック用の設定クラス（crawl_config_helper と同じ定義）
@dataclass
class MockCrawlerConfig:
    user_agent: str = "test-agent"
    request_timeout: int = 30
    parallel_downloads: int = 4


class TestCrawlConfigHelper:
    """crawl_config_helper のテスト。"""

    @pytest.fixture
    def base_config(self):
        return MockCrawlerConfig()

    def test_get_crawl_config_for_agency_exists(self, base_config):
        """存在する機関の設定を取得"""
        from crawler.utils.crawl_config_helper import get_crawl_config_for_agency, AWARD_URL_PATTERNS
        
        target = get_crawl_config_for_agency("test_agency", base_config)
        
        assert target is not None
        assert target.agency_key == "test_agency"
        assert target.name == "テスト機関"
        assert target.list_url == "https://test.example.com/list"
        assert target.detail_pattern == "https://test.example.com/detail/{id}"
        assert target.user_agent == "test-agent"
        assert target.timeout == 30
        assert target.parallel_downloads == 4

    def test_get_crawl_config_for_agency_missing_detail(self, base_config):
        """detail_pattern がない機関"""
        from crawler.utils.crawl_config_helper import get_crawl_config_for_agency
        
        target = get_crawl_config_for_agency("another_agency", base_config)
        
        assert target is not None
        assert target.detail_pattern == ""

    def test_get_crawl_config_for_agency_not_exists(self, base_config):
        """存在しない機関"""
        from crawler.utils.crawl_config_helper import get_crawl_config_for_agency
        
        target = get_crawl_config_for_agency("nonexistent", base_config)
        assert target is None

    def test_get_all_crawl_targets(self, base_config):
        """すべてのクロール対象を取得"""
        from crawler.utils.crawl_config_helper import get_all_crawl_targets
        
        targets = get_all_crawl_targets(base_config)
        
        assert isinstance(targets, dict)
        assert len(targets) == 2
        assert "test_agency" in targets
        assert "another_agency" in targets
        assert targets["test_agency"].name == "テスト機関"
        assert targets["another_agency"].name == "別機関"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])