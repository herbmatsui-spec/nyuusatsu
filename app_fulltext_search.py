"""
app_fulltext_search.py — 全文検索

仕様書PDFのテキストを横断検索する。
"""
import streamlit as st

from services.fulltext_search_service import FullTextSearchService
from database.engine import get_session
from database.repositories.bid_repository import BidRepository


def render():
    st.set_page_config(page_title="全文検索", page_icon="🔎", layout="wide")
    st.title("🔎 仕様書全文検索")
    st.caption("アーカイブされた仕様書を横断検索します。")

    db = next(get_session())
    try:
        bid_repo = BidRepository(db)
        bids = bid_repo.list_all(limit=200)
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        st.stop()

    docs = []
    for bid in bids:
        text = getattr(bid, "full_text", "") or ""
        if text:
            docs.append({"bid_id": bid.id, "filename": bid.filename, "text": text})

    searcher = FullTextSearchService()
    searcher.index(docs)

    query = st.text_input("検索キーワード")
    if query:
        results = searcher.search(query, limit=50)
        st.info(f"検索結果: {len(results)} 件")
        for r in results:
            with st.expander(f"{r['filename']} (bid_id={r['bid_id']})"):
                st.write(r.get("snippet", ""))
    else:
        st.info("キーワードを入力してください。")

    db.close()
