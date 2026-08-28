"""
Competitor Dashboard Page
🏢 競合分析ダッシュボードページを描画する。
"""
import logging
import streamlit as st
import pandas as pd
import plotly.express as px

logger = logging.getLogger(__name__)


def render_competitor_page():
    st.subheader("🏢 競合分析")
    st.caption("競合企業の落札実績を分析します")

    try:
        from database.engine import get_session
        from services.competitor_dashboard_service import CompetitorDashboardService
        from services.competitor_crud_service import CompetitorCrudService

        with get_session() as session:
            dash = CompetitorDashboardService(session)
            summary = dash.get_competitor_summary()

        total_competitors = len(summary)
        total_bids = sum(s["total_bids"] for s in summary)
        avg_rate = (
            sum(s["avg_award_rate"] or 0 for s in summary)
            / total_competitors
            if total_competitors > 0 else 0
        )
        target_count = sum(1 for s in summary if s["is_target"])

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("競合企業数", f"{total_competitors} 社")
        k2.metric("総落札件数", f"{total_bids:,} 件")
        k3.metric("平均落札率", f"{round(avg_rate, 1)}%" if avg_rate else "N/A")
        k4.metric("監視対象", f"{target_count} 社")

        st.divider()

        if not summary:
            st.info("データがありません。落札結果クロールを実行してください。")
            return

        df = pd.DataFrame(summary)
        df_display = df.rename(columns={
            "normalized_name": "企業名",
            "industry_category": "業種",
            "total_bids": "落札件数",
            "wins": "勝ち数",
            "win_rate": "勝率(%)",
            "avg_award_rate": "平均落札率(%)",
            "is_target_company": "監視対象",
        })

        st.caption("競合一覧")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        if "normalized_name" in df.columns:
            top10 = df.head(min(10, len(df)))
            fig = px.bar(
                top10,
                x="total_bids",
                y="normalized_name",
                title="🏆 落札件数 Top10",
                orientation="h",
                labels={"total_bids": "落札件数", "normalized_name": "企業名"},
                color="total_bids",
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)

        with st.expander("選択した競合の詳細"):
            options = {row["normalized_name"]: row["id"] for _, row in df.iterrows()}
            selected_name = st.selectbox("競合を選択", list(options.keys()))
            if selected_name:
                selected_id = options[selected_name]
                with get_session() as s2:
                    detail = CompetitorDashboardService(s2).get_competitor_detail(selected_id)
                if detail:
                    st.write(f"**{detail['name']}**")
                    st.write(f"- 業種: {detail['industry']}")
                    st.write(f"- 総勝利数: {detail['total_wins']}")
                    st.write(f"- 平均落札率: {detail['avg_award_rate']}%")

    except Exception as e:
        st.error(f"競合分析の読み込みに失敗しました: {e}")
        logger.error(f"Competitor dashboard error: {e}")
