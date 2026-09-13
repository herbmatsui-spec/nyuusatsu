"""
app_history.py — 抽出履歴画面

入札仕様書から抽出した結果の履歴を一覧・削除する Streamlit ページ。
app.py と同様の認証ゲートを持つ（ENABLE_AUTH=true の場合）。

起動方法:
    streamlit run app_history.py
"""
import streamlit as st
from dotenv import load_dotenv

from config_dir import AppConfig
from database.repositories.extraction_result_repository import ExtractionResultRepository
from utils.auth_decorator import is_authenticated
from utils.session_manager import get_session_manager
from utils.ui import inject_custom_css

load_dotenv()


def main() -> None:
    st.set_page_config(page_title="抽出履歴", page_icon="📜", layout="wide")
    inject_custom_css()
    config = AppConfig()

    # 認証ゲート
    if config.auth.enable_auth and not is_authenticated():
        st.warning("この画面を利用するにはログインが必要です。")
        if st.button("📋 抽出アプリへ戻る"):
            st.switch_page("app.py")
        st.stop()

    # サイドバー
    if is_authenticated():
        with st.sidebar:
            st.write(f"ようこそ、{st.session_state.get('username', 'unknown')} さん")
            if st.button("📋 抽出アプリ", use_container_width=True):
                st.switch_page("app.py")
            if st.button("📊 ダッシュボード", use_container_width=True):
                st.switch_page("app_dashboard.py")
            if st.button("🔓 ログアウト", use_container_width=True):
                sid = st.session_state.get("session_id")
                if sid:
                    get_session_manager().logout(sid)
                for key in ("authenticated", "username", "session_id"):
                    st.session_state.pop(key, None)
                st.rerun()

    st.title("📜 抽出履歴")

    repo = ExtractionResultRepository()
    results = repo.find_all(limit=100)

    if not results:
        st.info("まだ抽出結果がありません。")
        return

    st.caption(f"全 {len(results)} 件")
    for r in results:
        title = f"{r.get('filename')} — {(r.get('created_at') or '')[:16]}"
        with st.expander(title):
            st.json(r)
            if st.button("🗑 削除", key=f"del_{r.get('id')}"):
                if repo.delete(r.get("id")):
                    st.success("削除しました。")
                    st.rerun()
                else:
                    st.error("削除に失敗しました。")


if __name__ == "__main__":
    main()
