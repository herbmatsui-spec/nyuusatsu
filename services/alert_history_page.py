"""
Alert History Page
競合アラート履歴を表示するページ。
"""
import logging
import streamlit as st

logger = logging.getLogger(__name__)


def render_alert_history_page():
    st.subheader("🔔 アラート履歴")
    st.caption("競合出現アラートの履歴を確認します。")

    try:
        from database.engine import get_session
        from database.models import AlertHistory, Competitor
        import pandas as pd

        with get_session() as session:
            histories = (
                session.query(AlertHistory)
                .filter(AlertHistory.component.like("Competitor:%"))
                .order_by(AlertHistory.created_at.desc())
                .limit(200)
                .all()
            )

        if not histories:
            st.info("アラート履歴がありません。")
            return

        rows = []
        for h in histories:
            rows.append({
                "日時": h.created_at,
                "競合名": h.component.replace("Competitor:", "").strip(),
                "メッセージ": h.message,
                "重要度": h.severity,
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"アラート履歴の読み込みに失敗: {e}")
        logger.error(f"Alert history page error: {e}")
