"""
app_price_simulator.py — 価格シミュレータ

過去の落札価格データとLLMを用いて、適正入札価格・勝率を予測する。
"""
import streamlit as st

from database.engine import get_session
from services.price_prediction_service import PricePredictionService
from database.repositories.bid_repository import BidRepository
from database.models.competitor import Competitor


def render():
    st.set_page_config(page_title="価格シミュレータ", page_icon="💡", layout="wide")
    st.title("💡 適正入札価格・勝率予測")
    st.caption("過去データとLLMで入札戦略をシミュレートします。")

    db = next(get_session())
    try:
        bid_repo = BidRepository(db)
        service = PricePredictionService(db)
        bids = bid_repo.list_all(limit=100)
        competitors = db.query(Competitor).limit(50).all()
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        st.stop()

    if not bids:
        st.info("案件データがありません。")
        st.stop()

    bid_options = {f"{b.id} - {b.filename}": b.id for b in bids}
    selected_label = st.selectbox("対象案件", options=list(bid_options.keys()))
    selected_bid_id = bid_options.get(selected_label)

    competitor_options = {c.normalized_name: c.id for c in competitors}
    selected_competitors = st.multiselect("競合企業", options=list(competitor_options.keys()))

    bid_amount = st.number_input("入札予定価格（円）", min_value=0, value=0)

    if st.button("予測実行", type="primary") and selected_bid_id:
        comp_ids = [competitor_options[name] for name in selected_competitors]
        result = service.predict(selected_bid_id, comp_ids, bid_amount)
        if "error" in result:
            st.error(result["error"])
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("想定落札価格", f"{result.get('expected_price', 0):,} 円")
            col2.metric("予測勝率", f"{result.get('win_probability', 0)*100:.1f}%")
            col3.metric("理由", result.get("rationale", "-"))

    db.close()
