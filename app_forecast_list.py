"""
app_forecast_list.py — 発注見通し一覧画面 (Streamlit)

先行営業のため、公示前の発注見通しを一覧・検索できる管理画面。
"""
import streamlit as st
from datetime import datetime

from database.engine import get_session
from services.forecast_search_service import ForecastSearchService
from config import AppConfig


def render():
    st.set_page_config(page_title="発注見通し一覧", page_icon="📋", layout="wide")
    st.title("📋 発注見通し一覧")
    st.caption("公示前の発注予定を確認し、先行営業の準備を進められます。")

    db = next(get_session())
    try:
        service = ForecastSearchService(db)
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        st.stop()

    with st.sidebar:
        st.header("絞り込み")
        keyword = st.text_input("キーワード")
        category = st.text_input("業種カテゴリ")
        fiscal_year = st.number_input(
            "年度", min_value=2020, max_value=datetime.now().year + 2, value=datetime.now().year, step=1
        )
        status = st.selectbox("ステータス", ["", "draft", "published", "updated", "closed"], index=0)
        per_page = st.slider("表示件数", 10, 100, 20)

    items, total = service.search(
        keyword=keyword or None,
        category=category or None,
        fiscal_year=fiscal_year,
        status=status or None,
        page=1,
        per_page=per_page,
    )

    st.write(f"**該当件数: {total} 件**")
    for f in items:
        with st.container(border=True):
            st.write(f"**{f.title}** ({f.fiscal_year}年度)")
            cols = st.columns(3)
            cols[0].caption(f"カテゴリ: {f.category or '—'}")
            cols[1].caption(f"予算: {f.estimated_budget or '—'}")
            cols[2].caption(f"ステータス: {f.status}")
            if f.expected_publish_date:
                st.caption(f"📅 公示予定: {f.expected_publish_date.strftime('%Y-%m-%d')}")
            if f.description:
                st.write(f.description)

    db.close()


if __name__ == "__main__":
    render()
