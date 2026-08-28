"""
app_admin.py — 管理画面

組織・ユーザー・ロールの管理を行う。
"""
import streamlit as st

from database.engine import get_session
from services.auth_service import AuthService
from database.models.organization import Organization
from database.models.user import User
from database.models.role import Role
from config import AppConfig


def render():
    st.set_page_config(page_title="管理画面", page_icon="🛠", layout="wide")
    st.title("🛠 システム管理")
    tab1, tab2, tab3 = st.tabs(["組織", "ユーザー", "ロール"])

    with get_session() as session:
        auth = AuthService(session)

        with tab1:
            st.subheader("組織")
            with st.form("add_org"):
                name = st.text_input("組織名")
                code = st.text_input("コード")
                if st.form_submit_button("追加") and name:
                    org = Organization(name=name, code=code)
                    session.add(org)
                    session.commit()
                    st.rerun()
            for org in session.query(Organization).all():
                st.write(f"- {org.name} ({org.code})")

        with tab2:
            st.subheader("ユーザー")
            with st.form("add_user"):
                u_name = st.text_input("ユーザー名")
                u_pass = st.text_input("パスワード", type="password")
                u_email = st.text_input("メール")
                orgs = session.query(Organization).all()
                u_org = st.selectbox("組織", orgs, format_func=lambda o: o.name)
                if st.form_submit_button("追加") and u_name:
                    auth.create_user(u_name, u_pass, org_id=u_org.id if u_org else None, email=u_email)
                    session.commit()
                    st.rerun()
            for user in session.query(User).all():
                st.write(f"- {user.username} ({user.email})")

        with tab3:
            st.subheader("ロール")
            with st.form("add_role"):
                r_name = st.text_input("ロール名")
                r_perms = st.text_area("権限 (JSON)", value='["bid:read"]')
                if st.form_submit_button("追加") and r_name:
                    role = Role(name=r_name, permissions_json=r_perms)
                    session.add(role)
                    session.commit()
                    st.rerun()
            for role in session.query(Role).all():
                st.write(f"- {role.name}: {role.permissions_json}")
