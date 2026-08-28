"""
Qualification Stats Page
資格マッチの統計ダッシュボード。
"""
import logging
import streamlit as st
import pandas as pd

logger = logging.getLogger(__name__)


def render_qualification_stats_page():
    st.subheader("📊 資格マッチ統計")
    st.caption("自社資格での応募可能件数・不足状況を確認します。")

    try:
        from database.engine import get_session
        from database.models import BidQualificationTag, QualificationTag
        from sqlalchemy import func

        with get_session() as session:
            # Count bids by match status (simplified)
            total_bids = session.query(QualificationTag).count()

            df = pd.DataFrame({
                "category": ["全省庁統一資格", "地域等级", "業種"],
                "count": [0, 0, 0],
            })
            st.dataframe(df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"統計の取得に失敗: {e}")
        logger.error(f"Qualification stats error: {e}")