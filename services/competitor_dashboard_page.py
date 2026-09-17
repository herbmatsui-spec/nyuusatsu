import logging

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database.engine import get_session
from services.prediction_dashboard_service import PredictionDashboardService
from services.specification_similarity_service import SpecificationSimilarityService

logger = logging.getLogger(__name__)


def render_competitor_page():
    st.subheader("競合分析")
    tabs = st.tabs(["競合企業分析", "仕様書類似検索", "予測・難易度"])
    for tab, renderer in zip(tabs, [
        _render_competitor_analysis,
        _render_specification_similarity_search,
        _render_prediction_dashboard,
    ]):
        with tab:
            try:
                renderer()
            except Exception:
                logger.exception("Competitive analysis view failed")
                st.error("読み込みに失敗しました。データベースと設定を確認してください。")


def _render_competitor_analysis():
    from services.competitor_dashboard_service import CompetitorDashboardService

    with get_session() as session:
        summary = CompetitorDashboardService(session).get_competitor_summary()
    if not summary:
        st.info("競合データがありません。落札結果を登録してください。")
        return
    st.dataframe(pd.DataFrame(summary).rename(columns={
        "name": "企業名", "category": "業種", "total_bids": "応札記録数",
        "wins": "落札件数", "win_rate": "勝率(%)", "is_target": "監視対象",
    }), hide_index=True, use_container_width=True)
    fig = px.bar(pd.DataFrame(summary[:10]), x="wins", y="name", orientation="h",
                 labels={"wins": "落札件数", "name": "企業名"})
    st.plotly_chart(fig, use_container_width=True)
    options = {row["id"]: row["name"] for row in summary}
    selected = st.selectbox("競合を選択", list(options), format_func=options.get)
    with get_session() as session:
        detail = CompetitorDashboardService(session).get_competitor_detail(selected)
    if detail:
        st.write(detail["name"])
        st.metric("総勝利数", detail["total_wins"])


def _select_bid(prefix):
    keyword = st.text_input("案件IDまたはキーワード", key=f"{prefix}_keyword")
    with get_session() as session:
        service = SpecificationSimilarityService(session)
        if keyword.strip().isdigit():
            detail = service.get_bid_detail(int(keyword.strip()))
            bids = [detail] if detail else []
        else:
            bids = service.search_bids(keyword=keyword, limit=100)
    if not bids:
        st.info("対象案件がありません。仕様書を登録してください。")
        return None
    options = {bid["id"]: bid for bid in bids}
    selected = st.selectbox(
        "分析する案件", list(options), key=f"{prefix}_selected",
        format_func=lambda key: f"#{key} {options[key]['title'][:100]}",
    )
    st.session_state.selected_bid_id = selected
    return selected


def _render_specification_similarity_search():
    from services.prediction_model_config import get_config

    st.caption("仕様書が類似する入札案件（TF-IDF・文字n-gram、LLM呼び出しなし）")
    bid_id = _select_bid("similarity")
    if bid_id is None:
        return
    config = get_config()["similarity"]
    n = st.number_input("検索件数", 1, 50, int(config["default_n"]), key="sim_n")
    threshold = st.slider("最低類似度", 0.0, 1.0, float(config["default_threshold"]), key="sim_threshold")
    if st.button("類似度検索", key="sim_run"):
        with get_session() as session:
            results = SpecificationSimilarityService(session).find_similar_bids(
                bid_id, n=int(n), threshold=threshold, use_cache=False,
            )
        st.session_state.similarity_result = ((bid_id, n, threshold), results)
    stored = st.session_state.get("similarity_result")
    if stored and stored[0] == (bid_id, n, threshold):
        _display_similarity_results(stored[1])
        _render_similarity_feedback(bid_id, stored[1])


def _record_feedback(feedback_type, bid_id, rating, similar_bid_id=None):
    from services.feedback_logger import FeedbackLogger

    try:
        FeedbackLogger().log_feedback(
            feedback_type, int(bid_id), rating, similar_bid_id=similar_bid_id,
        )
        st.toast("フィードバックを記録しました。ご協力ありがとうございます。")
    except Exception:
        logger.exception("Feedback logging failed")
        st.warning("フィードバックを記録できませんでした。")


def _render_similarity_feedback(bid_id, results):
    st.caption("この類似検索結果は実際の案件と似ていますか？")
    col_helpful, col_not = st.columns(2)
    with col_helpful:
        if st.button("👍 役に立った", key="sim_fb_up"):
            _record_feedback("similarity", bid_id, 1)
    with col_not:
        if st.button("👎 役に立たなかった", key="sim_fb_down"):
            _record_feedback("similarity", bid_id, -1)


def _display_similarity_results(results):
    if not results:
        st.info("指定条件に一致する類似仕様書はありません。")
        return
    frame = pd.DataFrame(results).rename(columns={
        "similarity_score": "類似度スコア", "bid_id": "案件番号",
        "title": "タイトル", "organization_name": "発注機関",
        "announcement_date": "公開日", "awarded_company": "落札会社",
    })
    st.dataframe(frame, hide_index=True, use_container_width=True, column_config={
        "類似度スコア": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0),
    })


def _render_prediction_dashboard():
    bid_id = _select_bid("prediction")
    if bid_id is None:
        return
    company = st.text_input("自社名（未指定時は既定の自社設定）", key="prediction_company")
    with get_session() as session:
        service = PredictionDashboardService(session, company_name=company.strip() or None)
        result = service.get_bid_prediction(bid_id)
        company_name = service.company_name
    if result is None:
        st.info("案件が見つかりません。")
        return
    st.caption(f"対象企業: {company_name or '未設定（参考値）'}")
    _display_prediction(result)
    st.caption("この予測は役に立ちましたか？")
    col_helpful, col_not = st.columns(2)
    with col_helpful:
        if st.button("👍 役に立った", key="pred_fb_up"):
            _record_feedback("win_prediction", bid_id, 1)
    with col_not:
        if st.button("👎 役に立たなかった", key="pred_fb_down"):
            _record_feedback("win_prediction", bid_id, -1)


def _display_prediction(result):
    st.warning("ルールベースの参考推定です。統計的に校正された勝率や参加資格の判定ではありません。")
    difficulty = result["difficulty"]
    prediction = result["win_prediction"]
    rate = prediction["win_rate"]
    color = "green" if rate >= 0.30 else "orange" if rate >= 0.15 else "red"
    st.metric("入札難易度", f"{difficulty['score']:.1f} / 100")
    _render_confidence_note(difficulty.get("confidence"), "難易度スコアの根拠")
    st.progress(min(1.0, max(0.0, difficulty["score"] / 100)))
    figure = go.Figure(go.Indicator(
        mode="gauge+number", value=rate * 100, number={"suffix": "%"},
        title={"text": "予測勝率（参考）"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": color}},
    ))
    figure.update_layout(height=250, margin={"t": 50, "b": 10, "l": 30, "r": 30})
    st.plotly_chart(figure, use_container_width=True)
    _render_confidence_note(prediction.get("confidence"), "勝率予測の根拠")
    labels = {
        "budget": "予算額", "qualifications": "資格要件数", "deadline": "納期",
        "competition_rate": "過去競争率", "spec_length": "仕様書長さ",
        "company_win_rate": "自社過去勝率", "difficulty_inverse": "難易度逆相関",
        "agency_award_trend": "同機関の落札傾向", "qualification_match": "資格一致度",
    }
    for title, data in [("難易度の内訳", difficulty), ("勝率の内訳", prediction)]:
        rows = [{"要因": labels.get(key, key), "寄与度": value * data["weights"].get(key, 0) * 100}
                for key, value in data["breakdown"].items()]
        st.plotly_chart(px.bar(pd.DataFrame(rows), x="寄与度", y="要因", orientation="h", title=title),
                        use_container_width=True)


def _render_confidence_note(confidence, label):
    if not confidence:
        return
    missing = confidence.get("missing_factors") or []
    missing_context = confidence.get("missing_context") or []
    lines = [
        "算出方式: 根拠データの覆盖率ベースの重み付け平均（未校正・参考値）",
        f"根拠充足度: {confidence.get('evidence_coverage', 0) * 100:.0f}%",
    ]
    if missing:
        lines.append("根拠がないため既定値を使用した要素: " + "、".join(missing))
    if missing_context:
        lines.append("不足している案件情報: " + "、".join(missing_context))
    with st.popover(f"ℹ️ {label}"):
        for line in lines:
            st.write(line)
