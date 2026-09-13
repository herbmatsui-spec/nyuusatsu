import pytest
from crawler.parsers.agency_config_loader import AgencyConfigLoader

def test_load_existing_agency():
    # Load config for an agency defined in ehime.json
    loader = AgencyConfigLoader()
    config = loader.load("松山市")
    
    assert config["enabled"] is True
    assert "入札" in config["title_keywords"]
    assert "/shisei/denshinyusatsu/jouhou/" in config["url_includes"]

def test_load_non_existent_agency():
    # Load config for an agency not in any JSON
    loader = AgencyConfigLoader()
    config = loader.load("未知の市")
    
    # Should return default config
    assert config["enabled"] is True
    assert config["url_includes"] == []
    assert config["css_selectors"] == []

def test_cache_functionality():
    # Verify that subsequent calls use the cache
    loader = AgencyConfigLoader()
    
    # First call
    config1 = loader.load("松山市")
    # Modify the cache manually to see if it's returned
    loader.cache["松山市"] = {"cached": True}
    
    config2 = loader.load("松山市")
    assert config2["cached"] is True
