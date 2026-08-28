"""
Competitor Alert Config Page
監視する競合企業・業種・予算下限を設定するページ。
"""
import logging
import streamlit as st

logger = logging.getLogger(__name__)


def render_alert_config_page():
    st.subheader("🔔 競合アラート設定")
    st.caption("監視対象競合とアラート条件を設定します。")

    try:
        from database.engine import get_session
        from database.models import Competitor, CompetitorAlertConfig
        from sqlalchemy import select

        with get_session() as session:
            competitors = session.query(Competitor).order_by(Competitor.normalized_name).all()

        if not competitors:
            st.info("競合企業データがありません。先に落札結果をクロールしてください。")
            return

        comp_map = {c.normalized_name: c.id for c in competitors}
        selected = st.selectbox("監視対象競合を選択", list(comp_map.keys()))

        min_budget = st.number_input("最小予定価格（円）", min_value=0, value=0, step=100000)
        industry = st.selectbox("業種カテゴリ", ["すべて", "建設", "IT", "コンサル", "物品", "委託", "医療", "教育"])
        is_active = st.checkbox("アラート有効", value=True)

        if st.button("保存"):
            with get_session() as session:
                existing = session.query(CompetitorAlertConfig).filter(
                    CompetitorAlertConfig.competitor_id == comp_map[selected]
                ).first()
                data = {
                    "competitor_id": comp_map[selected],
                    "min_budget": min_budget,
                    "is_active": is_active,
                }
                if industry != "すべて":
                    data["industry_category"] = industry
                if existing:
                    for k, v in data.items():
                        setattr(existing, k, v)
                else:
                    session.add(CompetitorAlertConfig(**data))
                session.commit()
            st.success("アラート設定を保存しました。")

    except Exception as e:
        st.error(f"設定の保存に失敗: {e}")
        logger.error(f"Alert config page error: {e}")
