"""
Competitor Detail Page
個別競合の詳細情報を表示するページ。
"""
import logging
import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def render_competitor_detail_page(competitor_id: int):
    st.subheader("🏢 競合企業詳細")

    try:
        from database.engine import get_session
        from services.competitor_dashboard_service import CompetitorDashboardService

        with get_session() as session:
            dash = CompetitorDashboardService(session)
            detail = dash.get_competitor_detail(competitor_id)

        if not detail:
            st.warning("競合情報が見つかりません。")
            return

        st.write(f"## {detail['name']}")
        st.write(f"- 業種: {detail.get('industry', '不明')}")
        st.write(f"- 地域: {detail.get('region', '不明')}")
        st.write(f"- 監視対象: {'はい' if detail.get('is_target') else 'いいえ'}")

        tab1, tab2, tab3 = st.tabs(["落札実績", "推移", "メモ"])
        with tab1:
            wins = detail.get("wins", [])
            if wins:
                df = pd.DataFrame(wins)
                for col in ["budget_amount", "contract_amount"]:
                    if col in df.columns:
                        df[col] = df[col].apply(lambda x: f"{x:,}円" if x else "-")
                st.dataframe(df, use_container_width=True)
            else:
                st.info("落札実績がありません。")
        with tab2:
            with get_session() as s:
                trend = dash.get_competitor_trend(competitor_id, months=6)
            if trend:
                df_t = pd.DataFrame(trend)
                fig = px.line(df_t, x="month", y="wins", title="月別落札推移")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("推移データがありません。")
        with tab3:
            st.text_area("メモ", value=detail.get("memo", "") or "", height=200, disabled=True)

    except Exception as e:
        st.error(f"詳細の読み込みに失敗: {e}")
        logger.error(f"Competitor detail error: {e}")
