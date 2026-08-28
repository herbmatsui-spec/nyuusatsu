"""
Region Rank Page
地域别等级の管理・確認ページ。
"""
import logging
import streamlit as st

logger = logging.getLogger(__name__)


def render_region_rank_page():
    st.subheader("🗺️ 地域別資格等级")
    st.caption("各都道府県・地域での資格等级を確認・更新します。")

    try:
        from database.engine import get_session
        from database.models import CompanyProfile, CompanyRegionRank
        from config.region_filters import REGION_BLOCKS, get_prefecture_name

        with get_session() as session:
            profile = session.query(CompanyProfile).first()
            if not profile:
                st.info("先に「🏢 自社資格」から企業プロファイルを登録してください。")
                return

            ranks = (
                session.query(CompanyRegionRank)
                .filter(CompanyRegionRank.company_profile_id == profile.id)
                .all()
            )

        rank_map = {r.prefecture_code: r for r in ranks}

        st.write("#### 地方ブロック別一覧")

        for block_name, codes in REGION_BLOCKS.items():
            with st.expander(f"{block_name} ({len(codes)}件)"):
                for code in codes:
                    current = rank_map.get(code)
                    cols = st.columns([2, 2, 1])
                    name = get_prefecture_name(code)
                    cols[0].write(f"**{name}** ({code})")
                    cols[1].write(current.region_rank if current else "未登録")
                    cols[2].write(current.category if current else "-")

    except Exception as e:
        st.error(f"エラー: {e}")
        logger.error(f"Region rank page error: {e}")