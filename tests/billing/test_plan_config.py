from config import AppConfig, PlanConfig


def test_regional_prices_and_legacy_plan():
    config = AppConfig().plan
    assert config.PRICES[PlanConfig.SINGLE_REGION] == 5000
    assert config.PRICES[PlanConfig.DUAL_REGION] == 8000
    assert config.PRICES[PlanConfig.NATIONAL] == 24800
    assert config.LIMITS[PlanConfig.STANDARD]["prefectures"] == 47
    assert config.LIMITS[PlanConfig.FREE]["search_days"] == 7
    assert config.LIMITS[PlanConfig.SINGLE_REGION]["prefectures"] == 1
    assert config.LIMITS[PlanConfig.DUAL_REGION]["prefectures"] == 2


def test_price_ids_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_SINGLE_REGION", "price_single_test")
    monkeypatch.delenv("STRIPE_PRICE_DUAL_REGION", raising=False)
    config = PlanConfig()
    assert config.STRIPE_PRICE_IDS["single_region"] == "price_single_test"
    assert config.STRIPE_PRICE_IDS["dual_region"] == ""
