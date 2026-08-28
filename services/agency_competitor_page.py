"""
Agency Competitor Page
発注機関ごとの競合参入状況を表示する。
"""
import logging
import streamlit as st
import pandas as pd

logger = logging.getLogger(__name__)


def render_agency_competitor_page():
    st.subheader("🏛️ 発注機関×競合 マトリクス")
    st.caption("どの発注機関にどの競合が入札・落札しているか")

    try:
        from database.engine import get_session
        from services.competitor_dashboard_service import CompetitorDashboardService

        with get_session() as session:
            dash = CompetitorDashboardService(session)
            summary = dash.get_competitor_summary()

        if not summary:
            st.info("データがありません。")
            return

        df = pd.DataFrame(summary)
        agencies = sorted(df["agency_name"].dropna().unique().tolist())
        selected_agency = st.selectbox("発注機関を選択", ["すべて"] + agencies)

        filtered = df if selected_agency == "すべて" else df[df["agency_name"] == selected_agency]

        if not filtered.empty:
            chart_df = filtered[["normalized_name", "total_bids", "wins", "avg_award_rate"]].copy()
            chart_df = chart_df.rename(columns={"normalized_name": "企業名"})
            st.dataframe(chart_df, use_container_width=True, hide_index=True)
        else:
            st.info("選択した発注機関のデータがありません。")

    except Exception as e:
        st.error(f"エラー: {e}")
        logger.error(f"Agency competitor page error: {e}")
