"""
app_kanban.py — カンバンボード画面

Streamlit による案件進捗のカンバン表示。
"""
import streamlit as st

from database.engine import get_session
from services.kanban_service import KanbanService
from database.repositories.bid_repository import BidRepository
from config import AppConfig


def render():
    st.set_page_config(page_title="カンバンボード", page_icon="🗂", layout="wide")
    st.title("🗂 カンバンボード")
    st.caption("案件の進捗状況をドラッグで更新できます。")

    db = next(get_session())
    try:
        kanban_service = KanbanService(db)
        board = kanban_service.get_board()
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        st.stop()

    columns = AppConfig().kanban.columns
    cols = st.columns(len(columns))
    for idx, col_name in enumerate(columns):
        with cols[idx]:
            st.subheader(col_name)
            cards = board.get(col_name, [])
            for card in cards:
                with st.container(border=True):
                    st.write(f"**{card['filename']}**")
                    st.caption(card.get("organization_name") or "")
                    if card.get("budget"):
                        st.caption(f"💰 {card['budget']}")
                    if card.get("assignees"):
                        st.caption("👤 " + ", ".join(card["assignees"]))

    db.close()
