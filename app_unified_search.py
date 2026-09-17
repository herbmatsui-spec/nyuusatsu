import csv
import io
from datetime import date, datetime
from pathlib import Path

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from database.seeders.prefecture_seeder import PREFECTURES
from services.search_service import PAGE_SIZE, get_prefectures, search_bids
from utils.auth_decorator import get_current_user, is_authenticated
from utils.plan_gate import get_search_prefecture_scope


COLUMNS = {
    "id": st.column_config.NumberColumn("案件番号"),
    "title": st.column_config.TextColumn("タイトル", help="案件名（仕様書ファイル名）"),
    "organization": st.column_config.TextColumn("発注機関", help="自治体・省庁名"),
    "announcement_date": st.column_config.DateColumn("公開日", help="案件の公告日"),
    "budget_amount": st.column_config.NumberColumn(
        "予算額（円）", help="LLMが抽出した予定価格・予算上限。税区分は出典未確認のため未確認。例: 1000000",
        format="%,.0f",
    ),
    "qualification_requirements": st.column_config.TextColumn(
        "資格要件", help="LLMが抽出した参加資格要件（全文はセルにホバー）", width="medium",
    ),
    "delivery_deadline": st.column_config.DateColumn(
        "納期限", help="LLMが抽出した納品・履行期限（YYYY-MM-DD）",
    ),
    "deliverables": st.column_config.TextColumn(
        "成果物", help="LLMが抽出した成果物・作業内容（全文はセルにホバー）", width="medium",
    ),
}
PREFECTURE_NAMES = {row[0]: row[1] for row in PREFECTURES}
BID_TYPES = ["", "一般競争入札", "指名競争入札", "随意契約", "公募型プロポーザル", "その他"]
SORT_OPTIONS = {
    "id": "案件番号",
    "announcement_date": "公開日",
    "budget_amount": "予算額",
    "delivery_deadline": "納期限",
}


def load_css() -> None:
    path = Path(__file__).resolve().parent / "static/css/custom_unified_search.css"
    try:
        css = path.read_text(encoding="utf-8")
    except OSError:
        st.warning("スタイルファイルを読み込めないため、標準表示を使用します。")
        return
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def submit_search() -> None:
    budget_min = st.session_state.budget_min_input
    budget_max = st.session_state.budget_max_input
    if budget_min is not None and budget_max is not None and budget_min > budget_max:
        st.sidebar.error("予算額の最小値が最大値を超えています。最小値≤最大値で入力してください。")
        return
    st.session_state.search_conditions = {
        "keyword": st.session_state.keyword.strip(),
        "prefecture": list(st.session_state.prefecture),
        "organization": st.session_state.organization.strip(),
        "bid_type": st.session_state.bid_type or None,
        "use_or": st.session_state.use_or,
        "use_not": st.session_state.use_not,
        "budget_min": int(budget_min) if budget_min is not None else None,
        "budget_max": int(budget_max) if budget_max is not None else None,
        "qualification_keywords": st.session_state.qualification_keywords.strip(),
        "deadline_from": st.session_state.deadline_from,
        "deadline_to": st.session_state.deadline_to,
        "deliverables_keyword": st.session_state.deliverables_keyword.strip(),
        "sort_column": st.session_state.sort_column,
        "sort_direction": st.session_state.sort_direction,
    }
    st.session_state.current_page = 1


def _get_search_scope():
    user = get_current_user() if is_authenticated() else None
    return get_search_prefecture_scope(user)


def render_sidebar() -> None:
    with st.sidebar:
        st.header("検索条件")
        with st.form("unified_search_form"):
            keyword_column, or_column, not_column = st.columns([3, 1, 1])
            with keyword_column:
                st.text_input("キーワード", placeholder="検索キーワードを入力", key="keyword")
            with or_column:
                st.toggle("OR", key="use_or")
            with not_column:
                st.toggle("NOT", key="use_not")
            st.caption("通常は空白区切りのAND検索。NOTはORより優先し、いずれかの語を含む案件を除外します。")
            prefectures = sorted(set(PREFECTURE_NAMES) | set(get_prefectures(_get_search_scope())))
            st.multiselect(
                "都道府県", options=prefectures, key="prefecture",
                format_func=lambda code: PREFECTURE_NAMES.get(code, code),
            )
            st.text_input("発注機関", placeholder="発注機関名を入力", key="organization")
            st.selectbox(
                "入札方式", options=BID_TYPES, key="bid_type",
                format_func=lambda value: value or "すべて",
            )
            with st.expander("🔎 LLM抽出フィールドで絞り込み"):
                st.caption("金額の税区分は出典未確認のため未確認。例: 最小 1000000, 最大 5000000（単位: 円）")
                budget_min_column, budget_max_column = st.columns(2)
                with budget_min_column:
                    st.number_input(
                        "予算額（最小）", min_value=0, step=10_000, value=None,
                        key="budget_min_input", placeholder="1000000",
                    )
                with budget_max_column:
                    st.number_input(
                        "予算額（最大）", min_value=0, step=10_000, value=None,
                        key="budget_max_input", placeholder="5000000",
                    )
                st.text_input(
                    "資格要件キーワード", placeholder="例: 建設業許可 ISO 9001",
                    key="qualification_keywords",
                )
                st.caption("複数キーワードは空白区切りでAND検索されます。")
                deadline_from_column, deadline_to_column = st.columns(2)
                with deadline_from_column:
                    st.date_input(
                        "納期限（開始）", min_value=None, value=None, key="deadline_from",
                        format="YYYY-MM-DD",
                    )
                with deadline_to_column:
                    st.date_input(
                        "納期限（終了）", min_value=None, value=None, key="deadline_to",
                        format="YYYY-MM-DD",
                    )
                st.text_input(
                    "成果物キーワード", placeholder="例: 報告書", key="deliverables_keyword",
                )
            sort_column_column, sort_direction_column = st.columns(2)
            with sort_column_column:
                st.selectbox("並び替え", options=list(SORT_OPTIONS), format_func=lambda key: SORT_OPTIONS[key], key="sort_column")
            with sort_direction_column:
                st.selectbox("順序", options=["asc", "desc"], format_func=lambda value: "昇順" if value == "asc" else "降順", key="sort_direction")
            st.form_submit_button("検索", on_click=submit_search)


CSV_COLUMNS = {
    "id": "案件番号",
    "title": "タイトル",
    "organization": "発注機関",
    "announcement_date": "公開日",
    "budget_amount": "予算額（円）",
    "qualification_requirements": "資格要件",
    "delivery_deadline": "納期限",
    "deliverables": "成果物",
}


def results_to_csv(rows: list[dict]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS.values())
    for row in rows:
        values = []
        for key in CSV_COLUMNS:
            value = row.get(key)
            if key in ("announcement_date", "delivery_deadline") and value is not None:
                value = value.date() if isinstance(value, datetime) else value
                value = value.isoformat()
            text = "" if value is None else str(value)
            if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
                text = "'" + text
            values.append(text)
        writer.writerow(values)
    return buffer.getvalue().encode("utf-8-sig")


def render_results() -> None:
    conditions = st.session_state.get("search_conditions")
    placeholder = st.empty()
    if conditions is None:
        placeholder.info("検索キーワードを入力してください")
        return
    with placeholder.container():
        current_page = st.session_state.get("current_page", 1)
        scope = _get_search_scope()
        if scope == []:
            placeholder.warning("アクセスする都道府県が未選択です。プラン・請求ページで選択してください。")
            return
        with st.spinner("検索中..."):
            result = search_bids(
                **conditions, offset=(current_page - 1) * PAGE_SIZE, limit=PAGE_SIZE,
                allowed_prefectures=scope,
            )
            total_pages = max(1, (result["total"] + PAGE_SIZE - 1) // PAGE_SIZE)
            if current_page > total_pages:
                st.session_state.current_page = total_pages
                result = search_bids(
                    **conditions, offset=(total_pages - 1) * PAGE_SIZE, limit=PAGE_SIZE,
                    allowed_prefectures=scope,
                )
        st.session_state.search_results = result
        st.write(f"検索キーワード: {conditions['keyword']} (全{result['total']}件)")
        if not result["results"]:
            st.info("検索結果が見つかりませんでした")
            return
        if total_pages > 1:
            st.selectbox("ページ", range(1, total_pages + 1), key="current_page")
        st.caption(f"全{total_pages}ページ・1ページ{PAGE_SIZE}件。CSVは現在表示中のページのみです。")
        st.download_button(
            "CSVダウンロード", data=results_to_csv(result["results"]),
            file_name="search_results.csv", mime="text/csv", key="download_csv",
        )
        st.dataframe(result["results"], column_config=COLUMNS, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="統一検索ポータル", layout="wide")
    load_css()
    st.title("統一検索ポータル")
    try:
        render_sidebar()
        render_results()
    except SQLAlchemyError:
        st.error("検索データを取得できません。DB接続と alembic upgrade head の適用状況を確認してください。")


if __name__ == "__main__":
    main()
