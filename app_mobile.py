import json
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from services import mobile_ui_service as mobile_service


MOBILE_CSS = Path(__file__).resolve().parent / "static" / "css" / "mobile.css"


TABS = ("検索", "マイ検索", "お知らせ", "設定")


def init_page() -> None:
    st.set_page_config(
        page_title="入札システム モバイル",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    inject_mobile_css()


def inject_mobile_css() -> None:
    try:
        css = MOBILE_CSS.read_text(encoding="utf-8")
    except OSError:
        st.warning("モバイル用CSSを読み込めませんでした。既定のスタイルで表示します。")
        css = (
            '[data-testid="stMainBlockContainer"], .block-container {max-width:100%;padding:3rem 1rem 2rem;}'
            '[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none;}'
        )
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def navigate(tab: str) -> None:
    if tab not in TABS:
        raise ValueError("不明なタブです")
    st.session_state.current_tab = tab


PREFECTURES = dict(enumerate(
    "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県".split(),
    start=1,
))


def default_criteria() -> dict:
    today = date.today()
    year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    start = date(year, month, min(today.day, monthrange(year, month)[1]))
    return {"keyword": "", "prefectures": [], "organization": "", "start": start, "end": today}


def remember_criteria() -> None:
    st.session_state.mobile_criteria = {
        key: st.session_state[f"mobile_{key}"] for key in default_criteria()
    }


def reset_search() -> None:
    st.session_state.mobile_criteria = default_criteria()
    for key, value in default_criteria().items():
        st.session_state[f"mobile_{key}"] = value
    st.session_state.pop("mobile_results", None)
    st.session_state.pop("mobile_submitted", None)


def render_search() -> None:
    st.subheader("検索")
    criteria = st.session_state.setdefault("mobile_criteria", default_criteria())
    for key, value in criteria.items():
        st.session_state.setdefault(f"mobile_{key}", value)
    st.text_input("キーワード", placeholder="例：橋梁 補修", key="mobile_keyword", on_change=remember_criteria)
    codes = [13, 27, 23, 14, 40] + [code for code in PREFECTURES if code not in (13, 27, 23, 14, 40)]
    st.multiselect("都道府県", codes, format_func=PREFECTURES.get, key="mobile_prefectures", on_change=remember_criteria)
    st.caption("東京都・大阪府・愛知県・神奈川県・福岡県を先頭に表示しています。")
    st.text_input("発注機関（任意）", key="mobile_organization", on_change=remember_criteria)
    st.selectbox("入札方式", ["指定なし"], disabled=True, help="現在のデータモデルに入札方式がないため指定できません。")
    st.date_input("公開日（開始）", key="mobile_start", on_change=remember_criteria)
    st.date_input("公開日（終了）", key="mobile_end", on_change=remember_criteria)
    if st.button("検索する", type="primary", use_container_width=True):
        remember_criteria()
        if st.session_state.mobile_start > st.session_state.mobile_end:
            st.error("開始日は終了日以前を指定してください。")
        else:
            st.session_state.mobile_submitted = dict(st.session_state.mobile_criteria)
            run_search(reset_offset=True)
    results = st.session_state.get("mobile_results")
    has_more = bool(results and len(results["results"]) < results["total"])
    if has_more and st.button("もっと見る", use_container_width=True):
        run_search()
    render_results()


def run_search(reset_offset: bool = False) -> None:
    if reset_offset:
        st.session_state.mobile_offset = 0
    submitted = st.session_state.mobile_submitted
    offset = st.session_state.get("mobile_offset", 0)
    try:
        page = mobile_service.search(submitted, offset=offset)
    except Exception:
        if offset == 0:
            cache = st.session_state.get("mobile_cache")
            st.session_state.pop("mobile_results", None)
            if cache and cache["criteria"] == submitted:
                st.session_state.mobile_results = cache["page"]
                st.session_state.mobile_stale = True
            else:
                st.session_state.mobile_stale = False
                st.session_state.mobile_search_error = "検索データを取得できませんでした。時間をおいて再試行してください。"
        else:
            st.session_state.mobile_load_more_error = True
        return
    st.session_state.pop("mobile_load_more_error", None)
    st.session_state.pop("mobile_detail_id", None)
    if offset == 0:
        st.session_state.mobile_results = page
        st.session_state.mobile_cache = {"criteria": dict(submitted), "page": page, "fetched_at": datetime.now()}
    else:
        merged = st.session_state.mobile_results
        merged["results"] = merged["results"] + page["results"]
        st.session_state.mobile_results = merged
    st.session_state.mobile_offset = offset + mobile_service.PAGE_SIZE


def render_results() -> None:
    error = st.session_state.pop("mobile_search_error", None)
    if error:
        st.error(error)
        return
    if st.session_state.pop("mobile_stale", False):
        st.warning("⚠️ 古いデータです（取得失敗のためキャッシュを表示中）")
    cache = st.session_state.get("mobile_cache")
    if cache and (datetime.now() - cache["fetched_at"]).total_seconds() > 300:
        st.caption("キャッシュが5分以上前のものです。検索をやり直すと最新になります。")
    page = st.session_state.get("mobile_results")
    if page is None:
        return
    if not page["results"]:
        st.info("該当する案件はありません")
        st.button("検索条件をリセット", on_click=reset_search, use_container_width=True)
        return
    st.caption(f"該当 {page['total']:,} 件")
    for bid in page["results"]:
        with st.container(border=True):
            st.write(f"**案件番号 {bid['id']}**")
            st.write(bid.get("filename") or "名称未設定")
            st.caption(bid.get("organization_name") or "発注機関未設定")
            st.caption(f"公開日: {bid.get('announcement_date') or '不明'}")
            code = bid.get("prefecture_code")
            prefecture = PREFECTURES.get(int(code), str(code)) if str(code).isdigit() else "不明"
            st.caption(f"都道府県: {prefecture}")
            if st.button("詳細を見る", key=f"detail_{bid['id']}", use_container_width=True):
                st.session_state.mobile_detail_id = bid["id"]
            if st.session_state.get("mobile_detail_id") == bid["id"]:
                try:
                    record = mobile_service.detail(bid["id"])
                    if record is None:
                        st.warning("この案件は削除されています。")
                    else:
                        with st.expander("案件の全情報", expanded=True):
                            for name, value in record.items():
                                st.text(f"{name}: {value if value is not None else '未設定'}")
                except Exception:
                    st.error("詳細を取得できませんでした。")


def require_login() -> str | None:
    sid = st.session_state.get("mobile_session_id", "")
    if mobile_service.get_session_manager().validate_session(sid):
        return sid
    st.info("この機能を使うにはログインしてください。")
    with st.form("mobile_login"):
        username = st.text_input("ユーザー名")
        password = st.text_input("パスワード", type="password")
        if st.form_submit_button("ログイン", use_container_width=True):
            try:
                sid = mobile_service.login(username, password)
                if sid:
                    st.session_state.mobile_session_id = sid
                    st.rerun()
                st.error("ユーザー名またはパスワードが正しくありません。")
            except Exception:
                st.error("ログインできませんでした。時間をおいて再試行してください。")
    return None


def load_saved(criteria_json: str) -> None:
    try:
        criteria = json.loads(criteria_json)["mobile_ui"]
        criteria["start"] = date.fromisoformat(criteria["start"])
        criteria["end"] = date.fromisoformat(criteria["end"])
        if set(criteria) != set(default_criteria()):
            raise ValueError()
        if any(code not in PREFECTURES for code in criteria["prefectures"]):
            raise ValueError()
        st.session_state.mobile_criteria = criteria
        for key, value in criteria.items():
            st.session_state[f"mobile_{key}"] = value
        st.session_state.mobile_submitted = dict(criteria)
        navigate("検索")
        run_search()
    except (ValueError, KeyError, TypeError):
        st.session_state.mobile_saved_error = "この保存検索はモバイル形式ではないか、条件が不正です。"


def render_saved_searches() -> None:
    st.subheader("マイ検索")
    sid = require_login()
    if not sid:
        return
    st.caption("モバイル検索は条件の再利用用です。既存配信処理が未対応のため自動アラートは有効化しません。")
    if st.session_state.pop("mobile_saved_error", None):
        st.error("保存検索を読み込めませんでした。条件を確認してください。")
    if st.button("+ 新しい検索を保存", use_container_width=True):
        st.session_state.mobile_save_open = True
    if st.session_state.get("mobile_save_open"):
        with st.form("save_search"):
            name = st.text_input("検索名", max_chars=100)
            if st.form_submit_button("保存", use_container_width=True):
                try:
                    mobile_service.save_search(sid, name, st.session_state.get("mobile_criteria", default_criteria()))
                    st.session_state.mobile_save_open = False
                    st.rerun()
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("保存できませんでした。")
        if st.button("保存をキャンセル"):
            st.session_state.mobile_save_open = False
            st.rerun()
    try:
        rows = mobile_service.saved_searches(sid)
    except Exception:
        st.error("保存検索を取得できませんでした。")
        return
    if not rows:
        st.info("保存検索はありません。")
    for row in rows:
        with st.container(border=True):
            st.button(row["name"], key=f"saved_{row['id']}", on_click=load_saved, args=(row["criteria_json"],), use_container_width=True)
            with st.expander("編集・削除"):
                with st.form(f"edit_{row['id']}"):
                    name = st.text_input("検索名", value=row["name"], max_chars=100)
                    replace = st.checkbox("現在の検索条件で置き換える")
                    if st.form_submit_button("変更を保存"):
                        try:
                            criteria = st.session_state.get("mobile_criteria", default_criteria()) if replace else json.loads(row["criteria_json"])["mobile_ui"]
                            mobile_service.save_search(sid, name, criteria, row["id"])
                            st.rerun()
                        except Exception:
                            st.error("変更できませんでした。モバイル形式の条件か確認してください。")
                confirm = st.checkbox("この保存検索を削除する", key=f"confirm_{row['id']}")
                if st.button("削除を確定", disabled=not confirm, key=f"delete_{row['id']}"):
                    try:
                        mobile_service.delete_search(sid, row["id"])
                        st.rerun()
                    except Exception:
                        st.error("削除できませんでした。")


def render_notifications() -> None:
    st.subheader("お知らせ")
    st.button("設定を開く", on_click=navigate, args=("設定",), use_container_width=True)
    sid = require_login()
    if not sid:
        return
    st.button("すべて既読にする", disabled=True, use_container_width=True)
    st.info("通知の本文・送信履歴・既読状態を保存する仕組みが未実装です。過去のメール／LINE通知は表示できません。")


def logout() -> None:
    sid = st.session_state.pop("mobile_session_id", None)
    if sid:
        mobile_service.get_session_manager().logout(sid)
    st.session_state.pop("mobile_sync_job", None)


def render_settings() -> None:
    st.subheader("設定")
    sid = require_login()
    if not sid:
        return
    try:
        summary = mobile_service.account_summary(sid)
    except Exception:
        st.error("アカウント情報を取得できませんでした。")
        return
    with st.expander("📧 メール通知設定", expanded=False):
        channels = {c["channel_type"]: c for c in mobile_service.notification_channels(sid)}
        email = channels.get("email", {})
        current_dest = email.get("email_address") or (summary.get("username") + "@example.com")
        destination = st.text_input("通知先メールアドレス", value=current_dest, key="mobile_email_dest")
        active = st.toggle("メール通知を有効にする", value=bool(email.get("is_active")), key="mobile_email_toggle")
        st.caption("送信は毎朝8時の全体バッチ時に行われます。個別の時間帯指定には未対応です。")
        if st.button("メール設定を保存", key="mobile_email_save", use_container_width=True):
            try:
                mobile_service.set_notification_channel(sid, "email", active, destination.strip())
                st.success("メール設定を保存しました。")
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("メール設定を保存できませんでした。")
    with st.expander("💬 LINE通知設定", expanded=False):
        st.caption("LINE通知はシステム全体のトークン設定に依存し、友だち追加状況の取得APIはありません。")
        line = channels.get("line", {})
        if st.toggle("LINE通知を有効にする", value=bool(line.get("is_active")), key="mobile_line_toggle"):
            try:
                mobile_service.set_notification_channel(sid, "line", True)
                st.success("LINE通知を有効化しました（要システム設定）。")
            except Exception:
                st.error("LINE通知を有効化できませんでした。")
        elif line:
            try:
                mobile_service.set_notification_channel(sid, "line", False)
            except Exception:
                st.error("LINE通知を無効化できませんでした。")
    with st.expander("💳 プラン情報", expanded=False):
        st.write(f"**プラン**: {summary['plan_display']}")
        if summary["trial_active"]:
            st.caption(f"トライアル中（{summary['trial_ends_at']} まで）")
        st.caption(summary["next_billing_note"])
        st.link_button("請求ポータルを開く", "https://billing.stripe.com/p/login/", disabled=True)
        st.caption("モバイルからは請求ポータルへ直接遷移できません。デスクトップの「プラン・請求」をご利用ください。")
    with st.expander("🔄 データ同期"):
        st.caption("直近7日間の再取得ジョブを投入します。実行はサーバー側のワーカーが行います。")
        if st.button("最新データを再取得", use_container_width=True):
            try:
                job_id = mobile_service.enqueue_latest_refresh(sid)
                st.session_state.mobile_sync_job = job_id
                st.success(f"再取得ジョブ（ID: {job_id}）を投入しました。")
            except LookupError as exc:
                st.warning(str(exc))
            except Exception:
                st.error("ジョブを投入できませんでした。")
        job_id = st.session_state.get("mobile_sync_job")
        if job_id:
            try:
                status = mobile_service.job_status(job_id)
                st.caption(f"ジョブ {job_id}: 状態={status['status']} 取得={status['fetched_count']} 新規={status['new_count']} エラー={status['error_count']}")
            except Exception:
                st.caption(f"ジョブ {job_id}: 状態を取得できませんでした。")


def main() -> None:
    init_page()
    st.title("入札システム モバイル")
    st.session_state.setdefault("current_tab", TABS[0])
    st.radio("ナビゲーション", TABS, key="current_tab", horizontal=True)
    with st.container():
        {
            "検索": render_search,
            "マイ検索": render_saved_searches,
            "お知らせ": render_notifications,
            "設定": render_settings,
        }[st.session_state.current_tab]()


def render() -> None:
    main()


if __name__ == "__main__":
    main()
