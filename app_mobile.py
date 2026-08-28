"""
app_mobile.py — モバイル軽量UI

Streamlit のモバイル向け簡易ビュー。
"""
import streamlit as st

from database.engine import get_session
from services.bid_service import BidService
from database.repositories.bid_repository import BidRepository
from database.repositories.favorite_repository import FavoriteRepository


def render():
    st.set_page_config(page_title="入札システム モバイル", page_icon="📱", layout="centered")
    st.title("📱 入札システム モバイル")
    db = next(get_session())
    try:
        bid_repo = BidRepository(db)
        favorite_repo = FavoriteRepository(db)
        bid_service = BidService(bid_repo, favorite_repo)
        bids = bid_service.get_all_bids()
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        st.stop()

    st.metric("📋 総案件数", f"{len(bids):,} 件")
    status_counts = {}
    for bid in bids:
        s = bid.get("current_status", "未確認")
        status_counts[s] = status_counts.get(s, 0) + 1
    for status, count in status_counts.items():
        st.write(f"- {status}: {count} 件")

    st.subheader("最新案件")
    for bid in bids[:20]:
        st.write(f"**{bid.get('filename')}**")
        st.caption(bid.get("organization_name") or "")

    db.close()
