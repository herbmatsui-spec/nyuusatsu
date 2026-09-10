"""Billing page - Plan management and Stripe portal."""
from datetime import datetime
import streamlit as st
from utils.auth_decorator import is_authenticated, get_current_user
from services.billing_service import create_checkout_session, create_portal_session, get_effective_plan, is_trial_active
from config import PlanConfig


def render():
    if not is_authenticated():
        st.error("ログインしてください")
        st.stop()

    user = get_current_user()
    if not user:
        st.error("ユーザー情報が取得できません")
        st.stop()

    st.title("💳 プラン・請求管理")

    effective_plan = get_effective_plan(user)

    # Current plan display
    col1, col2, col3 = st.columns(3)
    col1.metric("現在のプラン", effective_plan.upper())
    col2.metric("月額料金", f"¥{PlanConfig.PRICES.get(user.plan, 0):,}")

    if is_trial_active(user):
        trial_days = (user.trial_ends_at - datetime.utcnow()).days
        col3.metric("トライアル残り", f"{trial_days}日")
        st.info(f"🎁 **無料トライアル中** ({effective_plan.upper()} 相当の全機能利用可能)")

    if user.current_period_end:
        st.caption(f"次回更新日: {user.current_period_end.strftime('%Y-%m-%d')}")

    st.divider()

    # Plan upgrade options
    st.subheader("プラン変更")

    plans = [PlanConfig.FREE, PlanConfig.STANDARD, PlanConfig.PRO, PlanConfig.ENTERPRISE]
    plan_names = {"free": "無料", "standard": "スタンダード", "pro": "プロ", "enterprise": "エンタープライズ"}
    current_idx = plans.index(user.plan) if user.plan in plans else 0

    for i, plan in enumerate(plans):
        if plan == user.plan:
            st.success(f"✅ {plan_names[plan]}（現在のプラン） - ¥{PlanConfig.PRICES[plan]:,}/月")
            with st.expander("プラン詳細"):
                limits = PlanConfig.LIMITS[plan]
                search_days = "無制限" if limits['search_days'] is None else f"{limits['search_days']}日"
                pdf_extract = "無制限" if limits['pdf_extract_daily'] is None else f"{limits['pdf_extract_daily']}件/日"
                api_req = "無制限" if limits['api_requests_monthly'] is None else f"{limits['api_requests_monthly']}件/月"
                export = "可" if limits['export'] else "不可"
                st.write(f"- 検索期間: {search_days}")
                st.write(f"- PDF抽出: {pdf_extract}")
                st.write(f"- APIリクエスト: {api_req}")
                st.write(f"- CSV/JSON出力: {export}")
            continue

        if i < current_idx:
            st.caption(f"⬇ {plan_names[plan]} - ¥{PlanConfig.PRICES[plan]:,}/月（ダウングレードは次回更新時に適用）")
        else:
            if st.button(f"⬆ {plan_names[plan]} にアップグレード - ¥{PlanConfig.PRICES[plan]:,}/月", key=f"upgrade_{plan}", use_container_width=True):
                try:
                    url = create_checkout_session(user, plan)
                    st.markdown(f"[決済ページへ進む]({url})", unsafe_allow_html=True)
                    st.info("別タブで決済ページが開きます。完了後、自動的にプランが更新されます。")
                except Exception as e:
                    st.error(f"決済セッション作成エラー: {e}")

    st.divider()

    # Billing portal
    st.subheader("請求書・支払い方法管理")
    st.caption("Stripe の請求ポータルで請求書の確認・支払い方法の変更・領収書のダウンロードができます。")

    if st.button("📄 Stripe請求ポータルを開く", use_container_width=True):
        try:
            url = create_portal_session(user)
            st.markdown(f"[請求ポータルへ]({url})", unsafe_allow_html=True)
            st.info("別タブで請求ポータルが開きます。")
        except Exception as e:
            st.error(f"請求ポータル作成エラー: {e}")


if __name__ == "__main__":
    from datetime import datetime
    render()