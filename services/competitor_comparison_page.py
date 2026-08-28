"""
Competitor Comparison Page
複数競合を横比較するページ。
"""
import logging
import streamlit as st
import pandas as pd
import plotly.express as px

logger = logging.getLogger(__name__)


def render_comparison_page():
    st.subheader("📊 競合比較")
    st.caption("2～3社の競合を選んで比較できます。")

    try:
        from database.engine import get_session
        from services.competitor_dashboard_service import CompetitorDashboardService

        with get_session() as session:
            dash = CompetitorDashboardService(session)
            summary = dash.get_competitor_summary()

        options = {s["name"]: s["id"] for s in summary}
        selected = st.multiselect("比較する競合を選択", list(options.keys()), max_selections=3)

        if not selected or len(selected) < 2:
            st.info("2社以上選択してください。")
            return

        selected_ids = [options[name] for name in selected]
        details = []
        with get_session() as s:
            dash2 = CompetitorDashboardService(s)
            for cid in selected_ids:
                d = dash2.get_competitor_detail(cid)
                if d:
                    details.append(d)

        compare_data = []
        for d in details:
            compare_data.append({
                "企業名": d["name"],
                "業種": d.get("industry"),
                "総勝利数": d.get("total_wins", 0),
                "平均落札率(%)": d.get("avg_award_rate"),
                "監視対象": "はい" if d.get("is_target") else "いいえ",
            })
        st.dataframe(pd.DataFrame(compare_data), use_container_width=True, hide_index=True)

        # radar chart
        if len(details) >= 2:
            radar_df = pd.DataFrame({
                "企業": [d["name"] for d in details],
                "総勝利数": [d.get("total_wins", 0) for d in details],
                "平均落札率": [d.get("avg_award_rate") or 0 for d in details],
            })
            fig = px.bar(
                radar_df,
                x="企業",
                y=["総勝利数", "平均落札率"],
                barmode="group",
                title="競合比較グラフ",
            )
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"比較画面の読み込みに失敗: {e}")
        logger.error(f"Comparison page error: {e}")
