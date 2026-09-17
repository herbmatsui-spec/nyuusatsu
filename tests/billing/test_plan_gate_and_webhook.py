"""Tests for prefecture access gating (plan_gate) and webhook plan sync."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from config import PlanConfig
from utils.plan_gate import can_access_prefecture, get_allowed_prefecture_count, get_allowed_prefectures
from services.billing_service import (
    _handle_subscription_canceled,
    adjust_prefectures_for_plan_change,
)


def make_db_session(user):
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = user
    return session


def make_user(plan, prefectures=None, trial_ends_at=None):
    return SimpleNamespace(
        id=1,
        plan=plan,
        trial_ends_at=trial_ends_at,
        allowed_prefectures=json.dumps(prefectures) if prefectures is not None else None,
    )


class TestCanAccessPrefecture:
    def test_national_allows_any_prefecture(self):
        assert can_access_prefecture(make_user(PlanConfig.NATIONAL), "01") is True
        assert can_access_prefecture(make_user(PlanConfig.NATIONAL), "47") is True

    def test_single_region_allows_first_selection(self):
        assert can_access_prefecture(make_user(PlanConfig.SINGLE_REGION), "13") is True

    def test_single_region_rejects_second_prefecture(self):
        user = make_user(PlanConfig.SINGLE_REGION, ["13"])
        assert can_access_prefecture(user, "27") is False

    def test_single_region_allows_selected_prefecture(self):
        user = make_user(PlanConfig.SINGLE_REGION, ["13"])
        assert can_access_prefecture(user, "13") is True

    def test_dual_region_allows_second_selection(self):
        user = make_user(PlanConfig.DUAL_REGION, ["13"])
        assert can_access_prefecture(user, "27") is True

    def test_dual_region_rejects_third_prefecture(self):
        user = make_user(PlanConfig.DUAL_REGION, ["13", "27"])
        assert can_access_prefecture(user, "40") is False

    def test_free_allows_one_prefecture_only(self):
        assert can_access_prefecture(make_user(PlanConfig.FREE), "13") is True
        user = make_user(PlanConfig.FREE, ["13"])
        assert can_access_prefecture(user, "27") is False

    def test_pro_allows_any_prefecture(self):
        assert can_access_prefecture(make_user(PlanConfig.PRO), "13") is True


class TestAllowedPrefectures:
    def test_count_follows_plan(self):
        assert get_allowed_prefecture_count(make_user(PlanConfig.FREE)) == 1
        assert get_allowed_prefecture_count(make_user(PlanConfig.SINGLE_REGION)) == 1
        assert get_allowed_prefecture_count(make_user(PlanConfig.DUAL_REGION)) == 2
        assert get_allowed_prefecture_count(make_user(PlanConfig.NATIONAL)) == 47

    def test_invalid_json_returns_empty_set(self):
        user = SimpleNamespace(id=1, plan=PlanConfig.SINGLE_REGION, trial_ends_at=None,
                               allowed_prefectures="not-json")
        assert get_allowed_prefectures(user) == set()

    def test_null_prefectures_returns_empty_set(self):
        user = make_user(PlanConfig.DUAL_REGION, None)
        assert get_allowed_prefectures(user) == set()


class TestAdjustPrefecturesForPlanChange:
    def test_upgrade_keeps_all_selections(self):
        user = make_user(PlanConfig.SINGLE_REGION, ["13"])
        result = adjust_prefectures_for_plan_change(user, PlanConfig.DUAL_REGION)
        assert result["adjusted"] is False
        assert user.allowed_prefectures == json.dumps(["13"])

    def test_downgrade_trims_excess_selections(self):
        user = make_user(PlanConfig.DUAL_REGION, ["13", "27"])
        result = adjust_prefectures_for_plan_change(user, PlanConfig.SINGLE_REGION)
        assert result["adjusted"] is True
        assert result["removed_prefectures"] == ["27"]
        assert json.loads(user.allowed_prefectures) == ["13"]

    def test_downgrade_within_limit_no_change(self):
        user = make_user(PlanConfig.DUAL_REGION, ["13"])
        result = adjust_prefectures_for_plan_change(user, PlanConfig.SINGLE_REGION)
        assert result["adjusted"] is False


class TestWebhookPlanSync:
    def test_subscription_updated_syncs_plan(self, monkeypatch):
        from services import billing_service
        monkeypatch.setattr(billing_service, "_get_config", lambda: SimpleNamespace(
            plan=SimpleNamespace(STRIPE_PRICE_IDS={"dual_region": "price_dual_test"}),
        ))
        user = SimpleNamespace(
            id=1, plan=PlanConfig.SINGLE_REGION, stripe_customer_id="cus_test",
            stripe_subscription_id=None, subscription_status=None, current_period_end=None,
            allowed_prefectures=json.dumps(["13"]),
        )
        session = make_db_session(user)
        sub = {
            "customer": "cus_test", "id": "sub_1", "status": "active",
            "current_period_end": 1700000000,
            "items": {"data": [{"price": {"id": "price_dual_test"}}]},
        }
        billing_service._handle_subscription_updated(session, sub)
        assert user.plan == "dual_region"
        assert json.loads(user.allowed_prefectures) == ["13"]

    def test_downgrade_webhook_trims_prefectures(self, monkeypatch):
        from services import billing_service
        monkeypatch.setattr(billing_service, "_get_config", lambda: SimpleNamespace(
            plan=SimpleNamespace(STRIPE_PRICE_IDS={"single_region": "price_single_test"}),
        ))
        user = SimpleNamespace(
            id=1, plan=PlanConfig.DUAL_REGION, stripe_customer_id="cus_test",
            stripe_subscription_id=None, subscription_status=None, current_period_end=None,
            allowed_prefectures=json.dumps(["13", "27"]),
        )
        session = make_db_session(user)
        sub = {
            "customer": "cus_test", "id": "sub_1", "status": "active",
            "current_period_end": 1700000000,
            "items": {"data": [{"price": {"id": "price_single_test"}}]},
        }
        billing_service._handle_subscription_updated(session, sub)
        assert user.plan == "single_region"
        assert json.loads(user.allowed_prefectures) == ["13"]

    def test_cancellation_resets_plan_and_prefectures(self):
        user = SimpleNamespace(
            id=1, plan=PlanConfig.DUAL_REGION, stripe_customer_id="cus_test",
            stripe_subscription_id="sub_1", subscription_status="active",
            current_period_end=1700000000, allowed_prefectures=json.dumps(["13", "27"]),
        )
        session = make_db_session(user)
        _handle_subscription_canceled(session, {"customer": "cus_test"})
        assert user.plan == PlanConfig.FREE
        assert user.allowed_prefectures is None
        assert user.stripe_subscription_id is None
