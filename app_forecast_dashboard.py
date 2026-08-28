"""
app_forecast_dashboard.py — 先行営業支援ダッシュボード (Streamlit)

発注見通しを営業担当者向けに可視化し、「興味あり」登録やアラート設定をできる。
"""
import streamlit as st
from datetime import datetime

from database.engine import get_session
from services.forecast_search_service import ForecastSearchService
from services.forecast_customer_link_service import ForecastCustomerLinkService
from services.forecast_report_service import ForecastReportService
from config import AppConfig


def render():
    st.set_page_config(page_title="発注見通しダッシュボード", page_icon="🎯", layout="wide")
    st.title("🎯 発注見通し 先行営業ダッシュボード")
    st.caption("公示前の発注予定から、自社が狙うべき案件を絞り込みます。")

    db = next(get_session())
    try:
        search_service = ForecastSearchService(db)
        report_service = ForecastReportService(db)
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        st.stop()

    # サマリー
    with st.sidebar:
        st.header("分析サマリー")
        status_summary = report_service.summary_by_status()
        for status, count in status_summary.items():
            st.write(f"- {status}: {count} 件")
        st.divider()
        st.subheader("カテゴリ別")
        cat_summary = report_service.summary_by_category(datetime.now().year)
        for cat, info in cat_summary.items():
            st.write(f"- {cat}: {info['count']} 件 / 予算 {info['total_budget']:,} 円")

    st.header("発注見通し一覧")
    keyword = st.text_input("キーワード検索")
    items, total = search_service.search(keyword=keyword or None, page=1, per_page=50)
    st.write(f"**該当: {total} 件**")

    # 顧客選択（興味あり登録用）
    link_service = ForecastCustomerLinkService(db)
    customers = db.query(__import__("database.models", fromlist=["Customer"]).Customer).all() if False else []
    try:
        from database.models import Customer
        customers = db.query(Customer).all()
    except Exception:
        customers = []

    for f in items:
        with st.container(border=True):
            cols = st.columns([3, 1, 1])
            cols[0].write(f"**{f.title}** ({f.fiscal_year}年度)")
            cols[1].caption(f"カテゴリ: {f.category or '—'}")
            cols[2].caption(f"予算: {f.estimated_budget or '—'}")

            if customers:
                customer = st.selectbox(
                    "興味あり登録（顧客）", [("", "—")] + [(str(c.id), c.name) for c in customers],
                    key=f"cust_{f.id}",
                )
                if customer and customer[0]:
                    if st.button("登録", key=f"reg_{f.id}"):
                        link_service.link(int(customer[0]), f.id)
                        st.success("登録しました")

            if f.description:
                st.write(f.description)

    db.close()


if __name__ == "__main__":
    render()
