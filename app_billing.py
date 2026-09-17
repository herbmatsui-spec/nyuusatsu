import json

import streamlit as st

from config import PlanConfig
from services.billing_service import (
    change_subscription_plan,
    create_checkout_session,
    create_portal_session,
    get_effective_plan,
    is_trial_active,
)
from utils.auth_decorator import get_current_user, is_authenticated


def render():
    if not is_authenticated():
        st.error("ログインしてください")
        st.stop()
    user = get_current_user()
    if not user:
        st.error("ユーザー情報が取得できません")
        st.stop()
    config = PlanConfig()
    effective = get_effective_plan(user)
    st.title("プラン・請求管理")
    st.metric("現在のプラン", config.DISPLAY_NAMES.get(effective, effective))
    st.metric("月額料金（税抜）", f"¥{config.PRICES.get(user.plan, 0):,}")
    if is_trial_active(user):
        st.info("無料トライアル中です")
    if user.current_period_end:
        st.caption(f"次回更新日: {user.current_period_end:%Y-%m-%d}")
    st.caption("既存契約の変更はアップグレード・ダウングレードとも次回更新時に反映されます。")
    st.warning("地域数が減る場合、変更反映時に超過する選択を解除します。都道府県を再確認してください。")
    for plan in (config.FREE, config.SINGLE_REGION, config.DUAL_REGION,
                 config.NATIONAL, config.PRO, config.ENTERPRISE):
        st.subheader(config.DISPLAY_NAMES[plan])
        st.write(f"月額 ¥{config.PRICES[plan]:,}（税抜） — {config.DESCRIPTIONS[plan]}")
        if plan == user.plan:
            st.success("現在のプラン")
            continue
        if not user.stripe_subscription_id and plan == config.FREE:
            continue
        configured = plan == config.FREE or bool(config.STRIPE_PRICE_IDS.get(plan))
        if st.button("このプランに変更", key=f"change_{plan}", disabled=not configured):
            try:
                if user.stripe_subscription_id:
                    change_subscription_plan(user, plan)
                    st.success("変更を予約しました。次回更新時に反映されます。")
                else:
                    url = create_checkout_session(user, plan)
                    st.link_button("決済ページへ進む", url)
            except Exception:
                st.error("プラン変更を受け付けられませんでした。予約済みの変更や支払い状況を請求ポータルで確認してください。")
        if not configured:
            st.caption("このプランの決済設定は準備中です。")

    if config.LIMITS.get(effective, config.LIMITS[config.FREE])["prefectures"] < 47:
        from database.engine import get_session
        from database.models.user import User
        from database.models._generated import Prefecture

        st.subheader("都道府県選択")
        limit = config.LIMITS[effective]["prefectures"]
        with get_session() as session:
            options = {p.code: p.name for p in session.query(Prefecture).order_by(Prefecture.code).all()}
        try:
            current = json.loads(user.allowed_prefectures or "[]")
            if not isinstance(current, list):
                current = []
        except (ValueError, TypeError):
            current = []
        selected = st.multiselect(
            "アクセスする都道府県", list(options),
            default=[code for code in current if code in options][:limit],
            format_func=lambda code: options[code], max_selections=limit,
        )
        if st.button("都道府県選択を保存"):
            with get_session() as session:
                stored = session.get(User, user.id)
                if stored is None:
                    st.error("ユーザーが見つかりません")
                    st.stop()
                stored.allowed_prefectures = json.dumps(selected)
                session.commit()
            st.success("都道府県選択を保存しました")

    st.subheader("請求書・支払い方法管理")
    if st.button("Stripe請求ポータルを開く"):
        try:
            st.link_button("請求ポータルへ", create_portal_session(user))
        except Exception:
            st.error("請求ポータルを開けませんでした。時間をおいて再度お試しください。")


if __name__ == "__main__":
    render()
