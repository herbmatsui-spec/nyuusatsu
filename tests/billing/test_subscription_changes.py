from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services import billing_service


@pytest.mark.parametrize("old_plan,new_plan", [("national", "single_region"), ("single_region", "dual_region")])
def test_plan_change_is_scheduled_for_next_cycle(monkeypatch, old_plan, new_plan):
    user = SimpleNamespace(
        id=1, plan=old_plan, stripe_customer_id="cus_test",
        stripe_subscription_id="sub_test", allowed_prefectures='["13", "27"]',
    )
    stripe = MagicMock()
    stripe.Subscription.retrieve.return_value = {
        "id": "sub_test", "customer": "cus_test", "status": "active",
        "schedule": None, "current_period_start": 100, "current_period_end": 200,
        "items": {"data": [{"id": "si_test", "price": {"id": "price_old"}, "quantity": 1}]},
    }
    stripe.SubscriptionSchedule.create.return_value = {"id": "sched_test"}
    monkeypatch.setattr(billing_service, "get_stripe_sync", lambda: stripe)
    monkeypatch.setattr(billing_service, "_get_config", lambda: SimpleNamespace(
        plan=SimpleNamespace(STRIPE_PRICE_IDS={new_plan: "price_new"}),
    ))

    assert billing_service.change_subscription_plan(user, new_plan) is True

    stripe.SubscriptionSchedule.create.assert_called_once_with(from_subscription="sub_test")
    stripe.SubscriptionSchedule.modify.assert_called_once_with(
        "sched_test", end_behavior="release", proration_behavior="none",
        phases=[
            {"start_date": 100, "end_date": 200,
             "items": [{"price": "price_old", "quantity": 1}], "proration_behavior": "none"},
            {"start_date": 200, "iterations": 1,
             "items": [{"price": "price_new", "quantity": 1}], "proration_behavior": "none"},
        ],
    )
    stripe.Subscription.modify.assert_not_called()
    assert user.plan == old_plan
    assert user.allowed_prefectures == '["13", "27"]'
