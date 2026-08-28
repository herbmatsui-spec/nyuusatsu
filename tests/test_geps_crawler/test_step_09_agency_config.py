from crawler.parsers.agency_config_loader import AgencyConfigLoader

def test_agency_config_default():
    """未知の自治体名にはデフォルト設定が返るか"""
    loader = AgencyConfigLoader()
    config = loader.load("存在しない自治体名_12345")
    assert config["enabled"] == True
    assert config["max_depth"] == 2

def test_agency_config_default_keys():
    """デフォルト設定に必要なキーがすべて含まれているか"""
    loader = AgencyConfigLoader()
    config = loader.load("不明な機関")
    required_keys = ["enabled", "url_includes", "title_keywords", "css_selectors", "max_depth"]
    for key in required_keys:
        assert key in config

def test_agency_config_cache():
    """同じ自治体名の2回目はキャッシュから返されるか"""
    loader = AgencyConfigLoader()
    config1 = loader.load("キャッシュテスト用")
    config2 = loader.load("キャッシュテスト用")
    assert config1 is config2  # 同一オブジェクトを返す

def test_agency_config_nonexistent_dir():
    """設定ディレクトリが存在しない場合デフォルト設定が返るか"""
    loader = AgencyConfigLoader(config_dir="/nonexistent/path/12345")
    config = loader.load("テスト省")
    assert config["enabled"] == True
