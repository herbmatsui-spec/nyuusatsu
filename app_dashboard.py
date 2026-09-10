"""
app_dashboard.py — 入札案件 分析ダッシュボード

Streamlit + Plotly によるダッシュボード UI。
フェーズ3 (Step 17-24) の全機能を1ファイルに実装。

起動方法:
    streamlit run app_dashboard.py
"""
import streamlit as st
import plotly.express as px
import pandas as pd
import json
import os
from datetime import date, timedelta, datetime
from dotenv import load_dotenv

from database.engine import get_session
from services.bid_service import BidService
from services.crawl_service import CrawlService
from database.repositories.bid_repository import BidRepository
from database.repositories.favorite_repository import FavoriteRepository
from config import AppConfig, PlanConfig
from utils.ui import inject_custom_css
from utils.auth_decorator import is_authenticated, get_current_user
from services.billing_service import get_effective_plan, is_trial_active
from utils.plan_gate import get_user_limits, require_feature, check_daily_limit

load_dotenv()

# ── Step 17: 基礎レイアウト ──────────────────────────────────────────

st.set_page_config(
    page_title="入札ダッシュボード",
    page_icon="📊",
    layout="wide",
)
inject_custom_css("custom_dashboard.css")

if "/welcome_dismissed" not in st.session_state:
    st.info("🏢 デモ環境です（ユーザーID=defaultで動作します）。右上の × で閉じられます。")
    if st.button("了解", key="dismiss_welcome"):
        st.session_state["welcome_dismissed"] = True
        st.rerun()

# Initialize session state for user
if "user_id" not in st.session_state:
    st.session_state.user_id = "default"

# Sidebar navigation
with st.sidebar:
    st.header("📋 メニュー")
    menu = st.radio(
        "表示する画面を選択",
        ["📊 概要", "📈 分析", "🔍 検索", "⭐ お気に入り", "🕒 履歴", "💰 コスト", "🔔 通知設定", "🏢 競合分析", "🛠 データ品質", "🔔 アラート履歴", "🏢 自社資格", "📄 仕様書アーカイブ", "📅 カレンダー", "🗂 カンバン", "💡 価格シミュレータ"],
        key="menu_selection"
    )
    st.caption("📊 概要: KPIと分布  /  📈 分析: 市場落札率  /  🔍 検索: 案件一覧  /  ⭐ お気に入り  /  🕒 履歴  /  💰 コスト  /  🔔 通知")
    st.divider()
    st.caption(
        "ステータス凡例: "
        "📥 未確認 → 🔍 検討中 → 📝 応募済 → 🏆 落札 / ❌ 失注"
    )
    st.divider()
    
    # Plan display
    if is_authenticated():
        user = get_current_user()
        if user:
            effective = get_effective_plan(user)
            plan_names = {"free": "無料", "standard": "スタンダード", "pro": "プロ", "enterprise": "エンタープライズ"}
            if is_trial_active(user):
                trial_days = (user.trial_ends_at - datetime.utcnow()).days
                st.sidebar.success(f"🎁 無料トライアル中 ({trial_days}日残り)")
                st.sidebar.caption(f"プラン: {plan_names.get(effective, effective).upper()} 相当")
            else:
                st.sidebar.info(f"📋 プラン: {plan_names.get(user.plan, user.plan).upper()}")
                if user.current_period_end:
                    st.sidebar.caption(f"次回更新: {user.current_period_end.strftime('%m/%d')}")
            if st.sidebar.button("💳 プラン変更", use_container_width=True):
                st.switch_page("app_billing.py")

# Initialize DB connection
try:
    db = next(get_session())
    bid_repo = BidRepository(db)
    favorite_repo = FavoriteRepository(db)
    bid_service = BidService(bid_repo, favorite_repo)
    crawl_service = CrawlService(db)
except Exception as e:
    st.error(f"データベース接続エラー: {e}")
    st.stop()

# ── メインコンテンツ ─────────────────────────────────────────────

if menu == "📊 概要":
    st.title("📊 入札案件 分析ダッシュボード")
    st.markdown("案件データの集計・可視化 ― リアルタイム統計")
    st.divider()
    
    with st.spinner("📊 データを集計中..."):
        # Get basic stats
        bids = bid_service.get_all_bids()
        total_bids = len(bids)
        
        # Status distribution
        status_counts = {}
        for bid in bids:
            status = bid.get("current_status", "未確認")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Win/Loss calculation
        win_count = status_counts.get("落札", 0)
        loss_count = status_counts.get("失注", 0)
        win_rate = round((win_count / (win_count + loss_count)) * 100, 1) if (win_count + loss_count) > 0 else 0
        
    # KPI Summary
    st.subheader("📈 KPI サマリー")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📋 総案件数", f"{total_bids:,} 件")
    k2.metric("🏆 落札率", f"{win_rate}%", delta=f"落札 {win_count} 件")
    k3.metric("📝 応募中", f"{status_counts.get('応募済', 0):,} 件")
    k4.metric("🔍 検討中", f"{status_counts.get('検討中', 0):,} 件")
    
    st.divider()
    
    # Graphs
    if status_counts:
        g1, g2 = st.columns(2)
        
        with g1:
            df_status = pd.DataFrame([
                {"status": k, "count": v} for k, v in status_counts.items()
            ])
            fig_status = px.pie(
                df_status, names="status", values="count",
                title="📊 ステータス分布",
                color_discrete_sequence=["#2563eb", "#f59e0b", "#10b981", "#ef4444", "#64748b"],
            )
            st.plotly_chart(fig_status, use_container_width=True)
            
        with g2:
            # 地域別案件数の集計
            def get_region(org_name):
                for pref in ["北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島", "茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川", "新潟", "富山", "石川", "福井", "山梨", "長野", "岐阜", "静岡", "愛知", "三重", "滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山", "鳥取", "島根", "岡山", "広島", "山口", "徳島", "香川", "愛媛", "高知", "福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄"]:
                    if pref in str(org_name):
                        if pref in ["東京", "京都", "大阪"]:
                            return pref + "府" if pref != "東京" else "東京都"
                        elif pref == "北海道":
                            return "北海道"
                        else:
                            return pref + "県"
                return "全国（省庁等）"

            regions = [get_region(b.get("organization_name") or "不明") for b in bids]
            df_region = pd.DataFrame({"region": regions})
            if not df_region.empty:
                df_region_counts = df_region.value_counts().reset_index()
                df_region_counts.columns = ["地域", "案件数"]
                fig_region = px.bar(
                    df_region_counts, x="地域", y="案件数",
                    title="🗺️ 地域別 案件数",
                    color_discrete_sequence=["#3b82f6"]
                )
                st.plotly_chart(fig_region, use_container_width=True)

        st.divider()
        
        # 自治体別の案件数 (Top 10)
        orgs = [b.get("organization_name") or "不明" for b in bids]
        df_org = pd.DataFrame({"agency": orgs})
        if not df_org.empty:
            df_org_counts = df_org.value_counts().reset_index()
            df_org_counts.columns = ["自治体/発注機関", "案件数"]
            df_org_top10 = df_org_counts.head(10)
            
            fig_org = px.bar(
                df_org_top10, x="案件数", y="自治体/発注機関",
                title="🏢 自治体・発注機関別 案件数 (Top 10)",
                orientation="h",
                color_discrete_sequence=["#10b981"]
            )
            # Y軸を降順にソートして見やすくする
            fig_org.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_org, use_container_width=True)

elif menu == "🔍 検索":
    st.title("🔍 案件検索")
    st.markdown("フィルタ条件を設定して案件を検索します。")

    # Plan gate for search
    user = get_current_user() if is_authenticated() else None
    limits = get_user_limits(user) if user else PlanConfig.LIMITS[PlanConfig.FREE]

    # 全案件からユニークな発注機関を取得してプルダウンに設定
    all_bids = bid_service.get_all_bids()
    org_list = sorted(list(set([str(b.get("organization_name") or "不明") for b in all_bids])))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        budget_q = st.text_input("予算キーワード")
    with col2:
        qual_q = st.text_input("資格キーワード")
    with col3:
        deadline_q = st.text_input("納期キーワード")
    with col4:
        org_filter = st.selectbox("発注機関 (自治体)", ["すべて"] + org_list)

    col_qual1, col_qual2, col_qual3 = st.columns(3)
    with col_qual1:
        grade_filter = st.selectbox("全省庁統一資格等级", ["すべて", "A", "B", "C", "D"], key="grade_filter")
    with col_qual2:
        region_filter = st.selectbox("地域ブロック", ["すべて", "北海道", "東北", "関東", "中部", "近畿", "中国", "四国", "九州・沖縄"], key="region_filter")
    with col_qual3:
        match_filter = st.selectbox("応募可否", ["すべて", "応募可能", "条件付き", "応募不可"], key="match_filter")

    my_only = st.checkbox("自社資格でフィルタ（応募可能のみ表示）", key="my_qualifications_only", value=False)

    filters = {}
    if budget_q: filters["budget"] = budget_q
    if qual_q: filters["qualifications"] = qual_q
    if deadline_q: filters["deadline"] = deadline_q
    if org_filter and org_filter != "すべて":
        filters["organization_name"] = org_filter

    # Free plan: limit search to last 7 days
    if limits["search_days"] is not None:
        cutoff_date = (datetime.utcnow() - timedelta(days=limits["search_days"])).strftime("%Y-%m-%d")
        filters["created_after"] = cutoff_date
        st.caption(f"ℹ️ 無料プランは直近 {limits['search_days']} 日のみ検索可能です")

    if st.button("検索実行"):
        results = bid_service.get_all_bids(filters)
        st.info(f"検索結果: {len(results)} 件")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

        # Export options - plan gated
        if results and limits["export"]:
            csv = pd.DataFrame(results).to_csv(index=False).encode('utf-8-sig')
            st.download_button("💾 CSVエクスポート", data=csv, file_name="search_results.csv", mime="text/csv")
        elif results and not limits["export"]:
            st.caption("🔒 CSV/JSONエクスポートはスタンダードプラン以上で利用可能です")


elif menu == "💰 コスト":
    from services.cost_dashboard_streamlit import render_cost_page
    render_cost_page()
elif menu == "⭐ お気に入り":
    st.title("⭐ お気に入り案件")
    st.markdown("スターを付けた案件を絞り込み・管理します。")

    user = get_current_user() if is_authenticated() else None
    limits = get_user_limits(user) if user else PlanConfig.LIMITS[PlanConfig.FREE]

    user_id = st.session_state.get("user_id", "default")
    favs = bid_service.list_favorites(user_id=user_id)

    col1, col2 = st.columns(2)
    with col1:
        fav_filter = st.text_input("案件名キーワード")
    with col2:
        export_format = st.selectbox("エクスポート形式", ["CSV", "JSON"], index=0)

    filtered_favs = []
    for fav in favs:
        if fav_filter and fav_filter not in str(fav.get("filename", "")):
            continue
        filtered_favs.append(fav)

    st.caption(f"お気に入り件数: {len(filtered_favs)}")
    if filtered_favs:
        st.dataframe(pd.DataFrame(filtered_favs))

        if limits["export"]:
            if export_format == "CSV":
                csv = pd.DataFrame(filtered_favs).to_csv(index=False).encode("utf-8-sig")
                st.download_button("💾 CSVエクスポート", data=csv, file_name="favorites.csv", mime="text/csv")
            else:
                json_bytes = json.dumps(filtered_favs, ensure_ascii=False, indent=2).encode("utf-8")
                st.download_button("💾 JSONエクスポート", data=json_bytes, file_name="favorites.json", mime="application/json")
        else:
            st.caption("🔒 CSV/JSONエクスポートはスタンダードプラン以上で利用可能です")

    st.divider()
    st.subheader("削除対象を選択")
    delete_target = st.selectbox("削除する案件", options=[str(fav.get("filename")) for fav in filtered_favs])
    if st.button("削除", type="primary") and delete_target:
        match = next((fav for fav in filtered_favs if str(fav.get("filename")) == delete_target), None)
        if match:
            favorite_repo.remove(match.get("bid_id"), user_id)
            st.success("お気に入りから削除しました。")
            st.rerun()

elif menu == "🕒 履歴":
    st.title("🕒 クロール履歴")
    st.markdown("巡回・PDF取得・分析の履歴を確認します。")

    limit = st.slider("表示件数", 10, 200, 50, 10)
    history = crawl_service.get_crawl_history(limit=limit)

    df_history = pd.DataFrame([
        {
            "日時": h.crawl_time,
            "URL件数": h.url_count,
            "新規件数": h.new_count,
            "ステータス": h.status,
            "エラー": h.error_message or "",
        }
        for h in history
    ])

    if not df_history.empty:
        df_history["ステータス"] = df_history["ステータス"].replace({"SUCCESS":"✅ SUCCESS","FAILED":"❌ FAILED"})
        status_filter = st.multiselect("ステータス", options=sorted(df_history["ステータス"].unique()))
        if status_filter:
            df_history = df_history[df_history["ステータス"].isin(status_filter)]

    st.dataframe(df_history, use_container_width=True, hide_index=True)
    if not df_history.empty:
        st.metric("実行回数", f"{len(df_history)} 回")
        st.metric("総URL件数", f"{int(df_history['URL件数'].sum()):,} 件")
        st.metric("総新規件数", f"{int(df_history['新規件数'].sum()):,} 件")

elif menu == "🔔 アラート履歴":
    from services.alert_history_page import render_alert_history_page
    render_alert_history_page()
elif menu == "🏢 競合分析":
    from services.competitor_dashboard_page import render_competitor_page
    render_competitor_page()
elif menu == "🛠 データ品質":
    st.title("🛠 データ品質")
    st.subheader("落札結果データの品質チェック")
    from services.award_quality_checker import get_quality_report
    with get_session() as session:
        report = get_quality_report(session)
    import pandas as pd
    cols = st.columns(4)
    cols[0].metric("総落札件数", f"{report.get('total_awards', 0)}")
    cols[1].metric("欠損落札率", f"{report.get('missing_award_rate', 0)} 件")
    cols[2].metric("欠損予算", f"{report.get('missing_budget', 0)} 件")
    cols[3].metric("欠損落札者", f"{report.get('missing_winner', 0)} 件")
    # 重複URL
    if report.get('duplicate_source_urls'):
        st.subheader("重複URL")
        df_dup = pd.DataFrame(report['details']['duplicates'])
        st.dataframe(df_dup)
    # 欠損例表示
    if report['details'].get('missing_award_rate'):
        st.subheader("落札率欠損例")
        st.dataframe(pd.DataFrame(report['details']['missing_award_rate']))
    if report['details'].get('missing_budget'):
        st.subheader("予算欠損例")
        st.dataframe(pd.DataFrame(report['details']['missing_budget']))
    if report['details'].get('missing_winner'):
        st.subheader("落札者欠損例")
        st.dataframe(pd.DataFrame(report['details']['missing_winner']))
elif menu == "🏢 自社資格":
    from services.company_profile_page import render_company_profile_page
    render_company_profile_page()
elif menu == "🔔 通知設定":
    from database.repositories.saved_search_repository import SavedSearchRepository
    from database.repositories.notification_channel_repository import NotificationChannelRepository
    from services.saved_search_service import SavedSearchService
    st.title("🔔 通知設定")
    st.markdown("巡回完了時の通知先と、毎朝アラート配信用の検索条件を管理します。")

    tab1, tab2 = st.tabs(["基本通知", "毎朝アラート配信"])

    with tab1:
        notify_type = crawl_service.get_setting("notify_type", "slack")
        notify_target = crawl_service.get_setting("notify_target", "")

        with st.form("notification_form"):
            new_type = st.selectbox("通知種別", ["slack", "email", "line"], index=["slack", "email", "line"].index(notify_type))
            new_target = st.text_input("通知先URL / メール / LINE Token", value=notify_target)
            submitted = st.form_submit_button("保存")
            if submitted:
                crawl_service.set_setting("notify_type", new_type)
                crawl_service.set_setting("notify_target", new_target)
                st.success("通知設定を保存しました。")

    with tab2:
        user_id = st.session_state.get("user_id", "default")
        saved_repo = SavedSearchRepository(db)
        channel_repo = NotificationChannelRepository(db)
        saved_service = SavedSearchService(db)

        with st.expander("💾 検索条件を保存"):
            with st.form("save_search_form"):
                s_name = st.text_input("条件名")
                s_keywords = st.text_input("キーワード")
                s_min_budget = st.number_input("最小予算", min_value=0, value=0)
                s_prefecture = st.text_input("都道府県")
                save_submitted = st.form_submit_button("保存")
                if save_submitted and s_name:
                    criteria = {}
                    if s_keywords:
                        criteria["keywords"] = s_keywords
                    if s_min_budget:
                        criteria["min_budget"] = int(s_min_budget)
                    if s_prefecture:
                        criteria["prefecture"] = s_prefecture
                    saved_service.create(user_id=user_id, name=s_name, criteria=criteria)
                    db.commit()
                    st.success("検索条件を保存しました。")
                    st.rerun()

        st.subheader("保存済み検索条件")
        saved_list = saved_repo.get_active_by_user(user_id)
        for s in saved_list:
            with st.expander(f"🔎 {s.name}"):
                st.json(s.criteria_json)
                if st.button("無効化", key=f"disable_{s.id}"):
                    s.is_active = False
                    db.commit()
                    st.rerun()

        st.subheader("通知チャネル")
        with st.form("add_channel_form"):
            c_type = st.selectbox("種別", ["slack", "teams", "email"])
            c_webhook = st.text_input("Webhook URL")
            c_email = st.text_input("メールアドレス")
            ch_submitted = st.form_submit_button("追加")
            if ch_submitted:
                channel_repo.create({
                    "user_id": user_id,
                    "channel_type": c_type,
                    "webhook_url": c_webhook,
                    "email_address": c_email,
                })
                db.commit()
                st.success("チャネルを追加しました。")
                st.rerun()

        channels = channel_repo.get_active_by_user(user_id)
        if channels:
            for ch in channels:
                st.write(f"- {ch.channel_type}: {ch.webhook_url or ch.email_address}")

elif menu == "📈 分析":
    st.title("📈 市場分析")
    from services.market_intel_service import MarketIntelService
    intel_service = MarketIntelService()
    
    st.subheader("業種別落札率")
    industry = st.selectbox("業種を選択", ["建設", "IT", "コンサル"])
    stats = intel_service.get_award_rate_by_industry(industry)
    st.metric(f"{industry}の平均落札率", f"{stats['avg_rate']}%")

elif menu == "💰 コスト":
    st.title("💰 API利用コスト")
    usage_file = "logs/api_usage.json"
    if os.path.exists(usage_file):
        with open(usage_file, "r", encoding="utf-8") as f:
            usage_data = json.load(f)
        df = pd.DataFrame(usage_data)
        st.dataframe(df)
        total_tokens = df["total_tokens"].sum() if not df.empty else 0
        st.metric("総利用トークン数", f"{total_tokens:,}")
    else:
        st.info("まだコストデータがありません。")

elif menu == "📄 仕様書アーカイブ":
    from services.archive_service import ArchiveService
    from database.repositories.bid_repository import BidRepository
    st.title("📄 仕様書アーカイブ")
    st.markdown("クロール時に保存されたPDF・仕様書をプレビュー・ダウンロードします。")

    bids = bid_service.get_all_bids()
    bid_options = {f"{b.get('id')} - {b.get('filename')}": b.get("id") for b in bids}
    selected_label = st.selectbox("案件を選択", options=list(bid_options.keys()))
    selected_bid_id = bid_options.get(selected_label)

    if selected_bid_id:
        archive_service = ArchiveService(db)
        archives = archive_service.get_archives_by_bid(selected_bid_id)
        if not archives:
            st.info("この案件のアーカイブはまだありません。")
        else:
            for arch in archives:
                with st.expander(f"📄 {arch.file_type.upper()} - {os.path.basename(arch.local_path)}"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("ファイルサイズ", f"{arch.file_size or 0:,} bytes")
                    col2.metric("保存日時", arch.archived_at.strftime("%Y-%m-%d %H:%M") if arch.archived_at else "-")
                    col3.metric("外部削除", "削除済" if arch.is_deleted_external else "存在")

                    if arch.file_type == "pdf" and os.path.exists(arch.local_path):
                        if st.button("PDFプレビュー", key=f"preview_{arch.id}"):
                            try:
                                import fitz
                                doc = fitz.open(arch.local_path)
                                page = doc.load_page(0)
                                pix = page.get_pixmap(dpi=150)
                                img_bytes = pix.tobytes("png")
                                st.image(img_bytes, caption="1ページ目プレビュー")
                                doc.close()
                            except Exception as exc:
                                st.error(f"PDFプレビュー失敗: {exc}")

                    with open(arch.local_path, "rb") as f:
                        st.download_button(
                            label="💾 ダウンロード",
                            data=f.read(),
                            file_name=os.path.basename(arch.local_path),
                            mime="application/octet-stream",
                            key=f"dl_{arch.id}",
                        )

            # Bulk ZIP download
            if len(archives) > 1:
                import zipfile, io as _io
                zip_buffer = _io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for arch in archives:
                        if os.path.exists(arch.local_path):
                            zf.write(arch.local_path, arcname=os.path.basename(arch.local_path))
                zip_buffer.seek(0)
                st.download_button(
                    label="📦 一括ダウンロード (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name=f"bid_{selected_bid_id}_archives.zip",
                    mime="application/zip",
                )

elif menu == "📅 カレンダー":
    from services.milestone_service import MilestoneService
    from services.ical_exporter import generate_ics
    st.title("📅 重要スケジュール")
    st.markdown("質問回答期限・提出期限・開札日を月間カレンダーで確認します。")

    days = st.slider("表示期間（日数）", 7, 90, 30)
    milestone_service = MilestoneService(db)
    upcoming = milestone_service.get_upcoming(days=days)

    if not upcoming:
        st.info("表示可能なマイルストーンがありません。")
    else:
        df = pd.DataFrame(upcoming)
        df["date"] = pd.to_datetime(df["date"])
        df["月"] = df["date"].dt.strftime("%Y-%m")
        month = st.selectbox("対象月", sorted(df["月"].unique()), index=len(df["月"].unique()) - 1)
        month_df = df[df["月"] == month].sort_values("date")

        for _, row in month_df.iterrows():
            with st.expander(f"{row['date'].strftime('%m/%d')} - {row['type']} - {row['filename']}"):
                st.write(f"**案件ID**: {row['bid_id']}")
                st.write(f"**種類**: {row['type']}")
                st.write(f"**日付**: {row['date'].strftime('%Y-%m-%d')}")

        ics_bytes = generate_ics(upcoming)
        st.download_button(
            "📥 iCalエクスポート (.ics)",
            data=ics_bytes,
            file_name="bid_milestones.ics",
            mime="text/calendar",
        )

elif menu == "🗂 カンバン":
    from services.kanban_service import KanbanService
    st.title("🗂 カンバンボード")
    st.markdown("案件の進捗状況をカンバンで管理します。")

    kanban_service = KanbanService(db)
    board = kanban_service.get_board()
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
                    new_status = st.selectbox(
                        "移動先",
                        options=columns,
                        index=columns.index(col_name),
                        key=f"move_{card['id']}_{col_name}",
                    )
                    if new_status != col_name:
                        try:
                            kanban_service.move_card(card["id"], new_status, "ui_user")
                            db.commit()
                            st.rerun()
                        except Exception as exc:
                            st.error(f"移動失敗: {exc}")

elif menu == "💡 価格シミュレータ":
    from services.price_prediction_service import PricePredictionService
    st.title("💡 適正入札価格・勝率予測")
    st.caption("過去データとLLMで入札戦略をシミュレートします。")
    bids = bid_service.get_all_bids()
    if not bids:
        st.info("案件データがありません。")
    else:
        bid_options = {f"{b.get('id')} - {b.get('filename')}": b.get("id") for b in bids}
        selected_label = st.selectbox("対象案件", options=list(bid_options.keys()))
        selected_bid_id = bid_options.get(selected_label)
        bid_amount = st.number_input("入札予定価格（円）", min_value=0, value=0)
        if st.button("予測実行", type="primary") and selected_bid_id:
            service = PricePredictionService(db)
            result = service.predict(selected_bid_id, [], bid_amount)
            if "error" in result:
                st.error(result["error"])
            else:
                col1, col2, col3 = st.columns(3)
                col1.metric("想定落札価格", f"{result.get('expected_price', 0):,} 円")
                col2.metric("予測勝率", f"{result.get('win_probability', 0)*100:.1f}%")
                col3.metric("理由", result.get("rationale", "-"))

db.close()
st.caption("入札案件 分析ダッシュボード ― Powered by Streamlit + Plotly")