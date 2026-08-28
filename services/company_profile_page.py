"""
Company Profile Page
自社資格情報の表示・編集ページ。
"""
import logging
import streamlit as st

logger = logging.getLogger(__name__)


def render_company_profile_page():
    st.subheader("🏢 自社資格マスター")
    st.caption("全省庁統一資格等级・地域別等级の登録を行います。")

    try:
        from database.engine import get_session
        from database.repositories.company_profile_repository import CompanyProfileRepository

        with get_session() as session:
            repo = CompanyProfileRepository(session)
            profiles = repo.session.query(repo.model).all() if hasattr(repo, "model") else []
            # Simple query
            from database.models import CompanyProfile
            profiles = session.query(CompanyProfile).all()

        if not profiles:
            st.info("企業プロファイルが登録されていません。")
            with st.form("new_profile"):
                name = st.text_input("企業名")
                grade = st.selectbox("全省庁統一資格等级", ["", "A", "B", "C", "D"])
                exp_date = st.date_input("資格有効期限", value=None)
                industry = st.text_input("主营業種")

                if st.form_submit_button("登録"):
                    with get_session() as s:
                        new_repo = CompanyProfileRepository(s)
                        new_repo.create({
                            "name": name,
                            "unified_qualification_grade": grade if grade else None,
                            "unified_qualification_expire": exp_date,
                            "industry_category": industry,
                        })
                    st.success("登録しました。")
                    st.rerun()
            return

        # Edit existing profile
        profile = profiles[0]
        with st.form("edit_profile"):
            name = st.text_input("企業名", value=profile.name)
            grade = st.selectbox(
                "全省庁統一資格等级",
                ["", "A", "B", "C", "D"],
                index=["", "A", "B", "C", "D"].index(profile.unified_qualification_grade or "") if profile.unified_qualification_grade else 0,
            )
            exp_date = st.date_input(
                "資格有効期限",
                value=profile.unified_qualification_expire or None,
            )
            industry = st.text_input("主营業種", value=profile.industry_category or "")

            if st.form_submit_button("更新"):
                with get_session() as s:
                    upd_repo = CompanyProfileRepository(s)
                    upd_repo.update(profile, {
                        "name": name,
                        "unified_qualification_grade": grade if grade else None,
                        "unified_qualification_expire": exp_date,
                        "industry_category": industry,
                    })
                st.success("更新しました。")
                st.rerun()

        # Region ranks management
        st.divider()
        st.subheader("地域別資格等级")
        with get_session() as s2:
            from database.models import CompanyRegionRank
            ranks = s2.query(CompanyRegionRank).filter(
                CompanyRegionRank.company_profile_id == profile.id
            ).all()

        for r in ranks:
            cols = st.columns([2, 2, 1])
            cols[0].write(r.prefecture_code)
            cols[1].write(r.region_rank or "未登録")
            cols[2].write(r.category or "-")

        with st.form("add_region_rank"):
            pref = st.text_input("都道府県コード（例: 13=東京都）")
            rank = st.text_input("地域等级（例: A, B, 1級等）")
            cat = st.text_input("業種（例: 建設）")

            if st.form_submit_button("追加"):
                from database.repositories.company_profile_repository import CompanyRegionRankRepository
                with get_session() as s3:
                    rr_repo = CompanyRegionRankRepository(s3)
                    rr_repo.create({
                        "company_profile_id": profile.id,
                        "prefecture_code": pref,
                        "region_rank": rank,
                        "category": cat,
                    })
                st.success("追加しました。")
                st.rerun()

    except Exception as e:
        st.error(f"エラー: {e}")
        logger.error(f"Company profile page error: {e}")