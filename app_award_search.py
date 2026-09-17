import streamlit as st
import pandas as pd
from services.award_search_service import search_award_results, get_company_win_rate, search_award_results_count, get_distinct_categories, get_prefecture_options, get_monthly_award_counts, get_participant_names
import datetime as dt

# ページ設定
st.set_page_config(
    page_title="落札情報検索",
    page_icon="🏆",
    layout="wide"
)

def main():
    # ページネーション設定
    PAGE_SIZE = 50
    
    # セッション状態の初期化
    if 'page_number' not in st.session_state:
        st.session_state.page_number = 1
    if 'total_results' not in st.session_state:
        st.session_state.total_results = 0
    if 'categories' not in st.session_state:
        # カテゴリのリストを取得（キャッシュ）
        st.session_state.categories = get_distinct_categories()

    # サイドバー
    with st.sidebar:
        st.header("落札情報検索")
        # 落札会社名入力ボックス
        award_company = st.text_input("落札会社名", placeholder="落札会社名を入力（部分一致（部分一致）")
        # 参加会社名入力ボックス
        participant_company = st.text_input("参加会社名", placeholder="参加会社名を入力（部分一致）")
        # 案件名入力ボックス（オプション）
        project_name = st.text_input("案件名", placeholder="案件名を入力（部分一致）")
        # 発注機関入力ボックス（オプション）
        agency_name = st.text_input("発注機関", placeholder="発注機関を入力（部分一致）")
        # 入札方式（カテゴリ）マルチセレクト
        category = st.multiselect(
            "業種カテゴリ",
            options=st.session_state.categories,
            default=[],
            help="複数選択可能"
        )
        prefecture_options = get_prefecture_options()
        prefectures = st.multiselect(
            "都道府県", options=list(prefecture_options),
            format_func=lambda code: prefecture_options[code],
        )
        st.caption("入札方式は保存項目がないため未対応です。地域は関連する入札の所在地です。")
        st.subheader("落札日付範囲")
        today = dt.date.today()
        three_months_ago = today - dt.timedelta(days=90)
        date_range = st.date_input(
            "落札日付範囲",
            value=(three_months_ago, today),
            max_value=today
        )
        # ページネーション
        st.subheader("ページネーション")
        col1, col2, col3 = st.columns([1,2,1])
        with col1:
            if st.button("← 前頁", disabled=st.session_state.page_number <= 1):
                st.session_state.page_number -= 1
                st.experimental_rerun()
        with col2:
            st.session_state.page_number = st.number_input("ページ番号", min_value=1, value=st.session_state.page_number, step=1)
        with col3:
            # 総件数から最終ページを計算し、最終ページでは次頁を無効化
            total_pages = (st.session_state.total_results + PAGE_SIZE - 1) // PAGE_SIZE
            next_disabled = st.session_state.page_number >= total_pages
            if st.button("次頁 →", disabled=next_disabled):
                st.session_state.page_number += 1
                st.experimental_rerun()
        # 検索ボタン
        if st.button("検索", type="primary"):
            st.session_state.search_executed = True
            st.session_state.page_number = 1  # ページをリセット
            # 検索条件を保存
            st.session_state.search_params = {
                "award_company": award_company,
                "participant_company": participant_company,
                "project_name": project_name,
                "agency_name": agency_name,
                "category": category,
                "prefectures": prefectures,
                "date_range": date_range if len(date_range) == 2 else None
            }
            # 総件数を取得
            with st.spinner("総件数を取得中..."):
                st.session_state.total_results = search_award_results_count(st.session_state.search_params)
        # 勝率表示
        if st.session_state.get('search_executed', False):
            # 会社名を決定（落札会社名優先）
            company_for_win_rate = st.session_state.get('search_params', {}).get('award_company') or st.session_state.get('search_params', {}).get('participant_company')
            if company_for_win_rate:
                with st.spinner("勝率を計算中..."):
                    win_rate_data = get_company_win_rate(company_for_win_rate)
                    st.subheader("勝率・受注率")
                    st.write(f"会社名: {company_for_win_rate}")
                    st.write(f"参加回数: {win_rate_data['participations']}")
                    st.write(f"優勝回数: {win_rate_data['wins']}")
                    st.write(f"勝率: {win_rate_data['win_rate']:.1f}%")

    # メインエリア
    st.title("落札情報検索結果")

    # 検索結果表示エリアの準備
    if 'search_executed' not in st.session_state:
        st.session_state.search_executed = False

    result_placeholder = st.empty()

    if st.session_state.search_executed:
        # 検索実行
        params = st.session_state.search_params
        offset = (st.session_state.page_number - 1) * PAGE_SIZE
        with st.spinner("検索中..."):
            results = search_award_results(params, offset=offset, limit=PAGE_SIZE)
            if results:
                df = pd.DataFrame([r.__dict__ for r in results])
                # 内部カラムを削除
                if '_sa_instance_state' in df.columns:
                    df = df.drop(columns=['_sa_instance_state'])
                # 参加会社名を AwardHistory/Competitor から取得
                participant_names = get_participant_names([r.id for r in results])
                df['participant_company'] = df['id'].map(participant_names).fillna("（記録なし）")
                # 表示カラムを選択およびリネーム
                display_columns = {
                    'id': 'ID',
                    'tender_id': '案件番号',
                    'project_name': '案件名',
                    'agency_name': '発注機関',
                    'winner_name': '落札会社名',
                    'participant_company': '参加会社名',
                    'winner_normalized': '正規化落札会社名',
                    'contract_amount': '落札金額',
                    'award_date': '落札日付'
                }
                # 月別落札件数の集計（ステップ11: 全検索結果対象の簡易チャート）
                monthly_counts = get_monthly_award_counts(params)
                # 存在するカラムのみ選択
                available_columns = {k: v for k, v in display_columns.items() if k in df.columns}
                df = df[list(available_columns.keys())].rename(columns=available_columns)
                st.dataframe(df, use_container_width=True)
                # ページネーション情報表示
                total_pages = (st.session_state.total_results + PAGE_SIZE - 1) // PAGE_SIZE
                st.caption(f"ページ {st.session_state.page_number} / {total_pages} （全 {st.session_state.total_results} 件）")
                # CSVダウンロードボタン（現在のページのみ）
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="CSVダウンロード",
                    data=csv,
                    file_name='award_search_results.csv',
                    mime='text/csv',
                )
                # 月別落札件数の簡易棒グラフ（結果下部）
                if monthly_counts:
                    st.subheader("月別落札件数")
                    st.bar_chart(monthly_counts)
            else:
                result_placeholder.info("検索結果がありません")
    else:
        result_placeholder.info("検索条件を入力してください")

if __name__ == "__main__":
    main()