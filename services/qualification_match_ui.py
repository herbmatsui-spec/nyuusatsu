"""
Qualification Match UI Components
マッチ结果のStreamlit表示コンポーネント集。
"""
import logging
from typing import Optional
import streamlit as st

logger = logging.getLogger(__name__)


def render_match_badge(can_apply: bool, match_level: str) -> str:
    """マッチ结果をバッジテキストで返す。"""
    if match_level == "full":
        return "🟢 完全一致"
    elif match_level == "partial":
        return "🟡 条件付き"
    else:
        return "🔴 応募不可"


def render_match_detail(match_result) -> None:
    """マッチ结果の詳細をexpanderPanel 表示。"""
    st.caption(f"スコア: {match_result.score:.0%} | {render_match_badge(match_result.can_apply, match_result.match_level)}")

    with st.expander("詳細"):
        if match_result.messages:
            for msg in match_result.messages:
                st.write(f"- {msg}")
        else:
            st.write("要件を全て充足しています。")


def render_filter_controls() -> dict:
    """ダッシュボード用资格フィルタUIControlをを描画。"""
    from config.qualification_grades import ALL_GRADES_LIST
    from config.region_filters import get_all_region_block_names

    col1, col2, col3 = st.columns(3)
    with col1:
        grade_filter = st.selectbox(
            "全省庁統一資格等级",
            ["すべて"] + ALL_GRADES_LIST,
            key="grade_filter",
        )
    with col2:
        region_filter = st.selectbox(
            "地域ブロック",
            ["すべて"] + get_all_region_block_names(),
            key="region_filter",
        )
    with col3:
        match_filter = st.selectbox(
            "応募可否",
            ["すべて", "応募可能", "条件付き", "応募不可"],
            key="match_filter",
        )

    my_only = st.checkbox("自社資格でフィルタ（応募可能のみ）", key="my_qualifications_only")

    return {
        "grade": grade_filter if grade_filter != "すべて" else None,
        "region": region_filter if region_filter != "すべて" else None,
        "match": match_filter if match_filter != "すべて" else None,
        "my_qualifications_only": my_only,
    }


def apply_match_filter(bids: list, match_results: dict) -> list:
    """bidsリストをmatches_resultsとフィルタ条件でフィルタリング。"""
    my_only = st.session_state.get("my_qualifications_only", False)
    match_filter = st.session_state.get("match_filter", "すべて")

    if not my_only and match_filter == "すべて":
        return bids

    filtered = []
    for bid in bids:
        result = match_results.get(bid["id"])
        if not result:
            continue

        if my_only and not result.can_apply:
            continue

        if match_filter == "応募可能" and result.match_level != "full":
            continue
        if match_filter == "条件付き" and result.match_level != "partial":
            continue
        if match_filter == "応募不可" and result.can_apply:
            continue

        filtered.append(bid)

    return filtered