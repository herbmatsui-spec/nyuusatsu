from datetime import datetime
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

import app_billing
from config import PlanConfig


@pytest.fixture
def billing_ui(monkeypatch):
    for plan in ("single_region", "dual_region", "national", "standard", "pro", "enterprise"):
        monkeypatch.setenv(f"STRIPE_PRICE_{plan.upper()}", f"price_{plan}_test")
    user = SimpleNamespace(
        id=1,
        plan="single_region",
        stripe_subscription_id="sub_test",
        current_period_end=datetime(2026, 10, 1),
        trial_ends_at=None,
        allowed_prefectures='["13"]',
    )
    st = MagicMock(spec=[
        "button", "caption", "error", "info", "link_button", "metric",
        "multiselect", "stop", "subheader", "success", "title", "warning", "write",
    ])
    st.button.return_value = False
    st.multiselect.return_value = ["13"]
    session = MagicMock()
    session.query.return_value.order_by.return_value.all.return_value = [
        SimpleNamespace(code="13", name="東京都"),
        SimpleNamespace(code="27", name="大阪府"),
    ]
    get_session = MagicMock()
    get_session.return_value.__enter__.return_value = session
    change_plan = MagicMock(return_value=True)
    checkout = MagicMock(return_value="https://example.com/checkout")
    portal = MagicMock(return_value="https://example.com/portal")
    monkeypatch.setattr(app_billing, "st", st)
    monkeypatch.setattr(app_billing, "is_authenticated", lambda: True)
    monkeypatch.setattr(app_billing, "get_current_user", lambda: user)
    monkeypatch.setattr(app_billing, "change_subscription_plan", change_plan)
    monkeypatch.setattr(app_billing, "create_checkout_session", checkout)
    monkeypatch.setattr(app_billing, "create_portal_session", portal)
    monkeypatch.setattr(import_module("database.engine"), "get_session", get_session)
    return SimpleNamespace(
        st=st, user=user, session=session, change_plan=change_plan,
        checkout=checkout, portal=portal,
    )


def click_button(ui, key):
    ui.st.button.side_effect = lambda label, **kwargs: (
        kwargs.get("key", label) == key and not kwargs.get("disabled", False)
    )


@pytest.mark.parametrize(
    "plan", ["free", "single_region", "dual_region", "national", "standard", "pro", "enterprise"],
)
def test_render_uses_instance_plan_dictionaries(billing_ui, plan):
    for name in ("DISPLAY_NAMES", "PRICES", "DESCRIPTIONS", "STRIPE_PRICE_IDS", "LIMITS"):
        assert not hasattr(PlanConfig, name)
    billing_ui.user.plan = plan
    config = PlanConfig()

    app_billing.render()

    assert billing_ui.st.metric.call_args_list == [
        call("現在のプラン", config.DISPLAY_NAMES[plan]),
        call("月額料金（税抜）", f"¥{config.PRICES[plan]:,}"),
    ]
    for offered in ("free", "single_region", "dual_region", "national", "pro", "enterprise"):
        billing_ui.st.subheader.assert_any_call(config.DISPLAY_NAMES[offered])
        billing_ui.st.write.assert_any_call(
            f"月額 ¥{config.PRICES[offered]:,}（税抜） — {config.DESCRIPTIONS[offered]}"
        )
    limit = config.LIMITS[plan]["prefectures"]
    if limit < 47:
        billing_ui.st.multiselect.assert_called_once()
        assert billing_ui.st.multiselect.call_args.kwargs["max_selections"] == limit
    else:
        billing_ui.st.multiselect.assert_not_called()
    billing_ui.st.error.assert_not_called()
    billing_ui.change_plan.assert_not_called()
    billing_ui.checkout.assert_not_called()


@pytest.mark.parametrize("target", ["dual_region", "national", "pro", "enterprise"])
def test_paid_upgrade_changes_subscription_without_checkout(billing_ui, target):
    click_button(billing_ui, f"change_{target}")

    app_billing.render()

    billing_ui.change_plan.assert_called_once_with(billing_ui.user, target)
    billing_ui.checkout.assert_not_called()
    billing_ui.st.link_button.assert_not_called()
    billing_ui.st.success.assert_any_call("変更を予約しました。次回更新時に反映されます。")
    billing_ui.st.error.assert_not_called()
    assert billing_ui.user.plan == "single_region"
    assert billing_ui.user.allowed_prefectures == '["13"]'


def test_free_user_without_subscription_starts_checkout(billing_ui):
    billing_ui.user.plan = "free"
    billing_ui.user.stripe_subscription_id = None
    billing_ui.user.current_period_end = None
    click_button(billing_ui, "change_single_region")

    app_billing.render()

    billing_ui.checkout.assert_called_once_with(billing_ui.user, "single_region")
    billing_ui.change_plan.assert_not_called()
    billing_ui.st.link_button.assert_called_once_with(
        "決済ページへ進む", billing_ui.checkout.return_value,
    )
    assert call("変更を予約しました。次回更新時に反映されます。") not in billing_ui.st.success.call_args_list
    billing_ui.st.error.assert_not_called()


@pytest.mark.parametrize("has_subscription", [True, False])
def test_plan_change_failure_shows_feedback_without_success(billing_ui, has_subscription):
    if has_subscription:
        service = billing_ui.change_plan
        unused_service = billing_ui.checkout
    else:
        billing_ui.user.plan = "free"
        billing_ui.user.stripe_subscription_id = None
        service = billing_ui.checkout
        unused_service = billing_ui.change_plan
    service.side_effect = RuntimeError("private billing error")
    click_button(billing_ui, "change_dual_region")

    app_billing.render()

    service.assert_called_once_with(billing_ui.user, "dual_region")
    unused_service.assert_not_called()
    billing_ui.st.error.assert_called_once_with(
        "プラン変更を受け付けられませんでした。予約済みの変更や支払い状況を請求ポータルで確認してください。"
    )
    assert billing_ui.st.success.call_args_list == [call("現在のプラン")]
    billing_ui.st.link_button.assert_not_called()


def test_portal_failure_shows_feedback_without_link(billing_ui):
    billing_ui.portal.side_effect = RuntimeError("private portal error")
    click_button(billing_ui, "Stripe請求ポータルを開く")

    app_billing.render()

    billing_ui.portal.assert_called_once_with(billing_ui.user)
    billing_ui.st.error.assert_called_once_with(
        "請求ポータルを開けませんでした。時間をおいて再度お試しください。"
    )
    billing_ui.st.link_button.assert_not_called()
    billing_ui.change_plan.assert_not_called()
    billing_ui.checkout.assert_not_called()
