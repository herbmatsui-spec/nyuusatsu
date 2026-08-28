"""
入札仕様書PDF要件抽出アプリ（プロトタイプ）
官公庁・自治体の入札仕様書PDFから、業務代行判断に必要な必須要件を
DeepSeek APIを用いて自動抽出し、Streamlitで可視化する社内用Webアプリ。
"""
import json
import os
import traceback
import uuid
from typing import Any, Dict, Optional

import streamlit as st
from dotenv import load_dotenv

from config import AppConfig
from database.repositories.extraction_result_repository import ExtractionResultRepository
from services.analysis_service_core import AnalysisServiceCore, LLMAnalysisError
from services.pdf_processor import PDFExtractionError, PDFProcessor
from utils.auth_decorator import is_authenticated
from utils.logger import setup_logging
from utils.request_throttler import get_request_throttler
from utils.security import validate_file_upload
from utils.session_manager import get_session_manager
from utils.ui import inject_custom_css, page_header


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
TEXT_PREVIEW_LIMIT = 2000
FILE_MAX_SIZE_MB = 20

# -----------------------------------------------------------------------------
# Page Setup
# -----------------------------------------------------------------------------

def init_page() -> None:
    st.set_page_config(
        page_title="入札仕様書 要件抽出アプリ",
        page_icon="📋",
        layout="wide",
    )
    setup_logging()
    load_dotenv()
    inject_custom_css()


def get_api_key() -> Optional[str]:
    """DEEPSEEK_API_KEY を取得する"""
    try:
        key = st.secrets.get("DEEPSEEK_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("DEEPSEEK_API_KEY")


def get_gemini_key() -> Optional[str]:
    try:
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


def show_login_screen(config: AppConfig) -> bool:
    """ログイン画面を表示し、認証成功時にセッション状態を書き込む。"""
    st.markdown("## 🔐 ログイン")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("ユーザー名")
        password = st.text_input("パスワード", type="password")
        if st.button("ログイン", type="primary"):
            from database.engine import get_session
            from services.auth_service import AuthService
            with get_session() as session:
                auth = AuthService(session, config)
                user = auth.authenticate(username, password)
                if user:
                    token = auth.create_token(user)
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.auth_token = token
                    st.session_state.session_id = get_session_manager(
                        config.auth.session_timeout_minutes
                    ).create_session(username)
                    return True
            st.error("ユーザー名またはパスワードが正しくありません")
    return False


# -----------------------------------------------------------------------------
# UI Components
# -----------------------------------------------------------------------------

def show_result(result: Dict[str, Any]) -> None:
    st.subheader("🔎 抽出結果サマリ")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("💰 予算・予定価格", label_visibility="visible", value=result.get("budget", "記載なし"))
    with col2:
        st.metric("📅 納期・履行期間", label_visibility="visible", value=result.get("deadline", "記載なし"))

    st.divider()
    st.markdown(f"<div class='card'><div class='card-title'>📜 参加資格</div>{result.get('qualifications', '記載なし')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card'><div class='card-title'>📦 成果物・作業内容</div>{result.get('deliverables', '記載なし')}</div>", unsafe_allow_html=True)
    st.caption(f"（{len(result.get('deliverables', ''))}文字）")
    st.divider()

    with st.expander("🧾 JSONデータ（生）"):
        st.json(result)

    json_bytes = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button(
        label="💾 結果をJSONでダウンロード",
        data=json_bytes,
        file_name="extracted_requirements.json",
        mime="application/json",
        type="primary"
    )


def save_extraction_result(
    result: Dict[str, Any],
    filename: str,
    username: Optional[str] = None,
) -> int:
    """抽出結果を DB に保存し、保存されたレコードの ID を返す。"""
    repo = ExtractionResultRepository()
    data = {
        "filename": filename,
        "budget": result.get("budget", "記載なし"),
        "qualifications": result.get("qualifications", "記載なし"),
        "deadline": result.get("deadline", "記載なし"),
        "deliverables": result.get("deliverables", "記載なし"),
        "raw_text_length": len(result.get("deliverables", "")),
        "created_by": username,
    }
    return repo.save(data)


# -----------------------------------------------------------------------------
# Main App
# -----------------------------------------------------------------------------

def main() -> None:
    init_page()
    config = AppConfig()
    # 設定バリデーション
    errors = config.validate()
    if errors:
        import warnings
        for err in errors:
            warnings.warn(err)
            st.warning(f"設定警告: {err}")

    # DB スキーマ確保（抽出結果テーブル等の自動作成）
    try:
        from database.base import Base
        from database.engine import engine
        Base.metadata.create_all(bind=engine)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"DBスキーマの確保に失敗しました: {exc}")

    # 認証ゲート
    if config.auth.enable_auth and not is_authenticated():
        if show_login_screen(config):
            st.rerun()
        st.stop()

    # サイドバー（認証時のみ表示）
    if is_authenticated():
        with st.sidebar:
            st.write(f"ようこそ、{st.session_state.get('username', 'unknown')} さん")
            if st.button("📜 履歴", use_container_width=True):
                st.switch_page("app_history.py")
            if st.button("🔓 ログアウト", use_container_width=True):
                sid = st.session_state.get("session_id")
                if sid:
                    get_session_manager().logout(sid)
                for key in ("authenticated", "username", "session_id"):
                    st.session_state.pop(key, None)
                st.rerun()

    st.markdown(
        "<div class='lp-hero'><h1>📋 入札仕様書 要件抽出アプリ</h1>"
        "<p>予算 / 参加資格 / 納期 / 成果物を LLM が自動抽出。業務代行判断を1秒で。</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "官公庁・自治体の入札仕様書PDFをアップロードすると、"
        "業務代行判断に必要な **予算 / 参加資格 / 納期 / 成果物** を DeepSeek API で自動抽出します。"
    )

    nav1, nav2 = st.columns([5, 1])
    with nav2:
        if st.button("📊 ダッシュボード", use_container_width=True):
            st.switch_page("app_dashboard.py")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='lp-step'><h3>1. PDFをアップロード</h3><p>仕様書PDFを選択するだけ</p></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='lp-step'><h3>2. LLMが自動抽出</h3><p>DeepSeek/Gemini が必須要件を解析</p></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='lp-step'><h3>3. 結果を確認・DL</h3><p>JSON形式で即ダウンロード</p></div>", unsafe_allow_html=True)


    # APIキーの取得（AnalysisServiceCore内部で処理されるが、UI上の警告用にチェック）
    deepseek_key = get_api_key()
    gemini_key = get_gemini_key()
    
    if not deepseek_key and not gemini_key:
        st.markdown(
            "<div style='border-left:4px solid var(--color-danger,#ef4444);background:#fef2f2;padding:16px;border-radius:8px;'>"
            "<strong>🔑 APIキー未設定</strong><br>"
            "<code>.env</code> に <code>DEEPSEEK_API_KEY</code> または <code>GEMINI_API_KEY</code> を設定してください。"
            "</div>", unsafe_allow_html=True
        )
        st.stop()

    # アプリ側レートリミット（利用者ごとの過剰リクエスト抑制）
    if config.rate_limit.enable_rate_limit:
        client_key = st.session_state.get("username") or "anonymous"
        throttler = get_request_throttler(
            max_requests=config.rate_limit.max_requests_per_minute,
            window_seconds=60,
        )
        if not throttler.is_allowed(client_key):
            reset = throttler.get_reset_in_seconds(client_key)
            st.error(
                f"⚠️ リクエスト上限（{config.rate_limit.max_requests_per_minute}/分）に達しました。"
                f"約 {reset} 秒後に再試行してください。"
            )
            st.stop()
        st.caption(
            f"残りリクエスト: {throttler.get_remaining(client_key)}/"
            f"{config.rate_limit.max_requests_per_minute}（1分間）"
        )

    uploaded_file = st.file_uploader("📄 入札仕様書PDFを選択（20MBまで）", type=["pdf"])
    if uploaded_file is None:
        st.markdown(
            "<div style='text-align:center;padding:48px;border:2px dashed #cbd5e1;border-radius:16px;color:var(--color-muted,#64748b);'>"
            "<div style='font-size:48px;'>📄⬆️</div>"
            "<h3>入札仕様書PDFをドラッグ＆ドロップ</h3>"
            "<p>または下のボタンから選択してください</p></div>", unsafe_allow_html=True
        )
        st.stop()

    error_msg = validate_file_upload(uploaded_file)
    if error_msg:
        st.error(f"⚠️ {error_msg}")
        st.stop()

    pdf_bytes = uploaded_file

    progress = st.progress(0, text="準備中…")
    progress.progress(20, text="PDFを読み込んでいます…")
    try:
        processor = PDFProcessor(config)
        text = processor.extract_text(pdf_bytes, source_name=uploaded_file.name)
        progress.progress(100, text="テキスト抽出完了")
    except PDFExtractionError as exc:
        st.error(f"⚠️ {exc}")
        st.stop()

    with st.expander("📄 抽出テキストのプレビュー"):
        preview = text if len(text) <= TEXT_PREVIEW_LIMIT else text[:TEXT_PREVIEW_LIMIT] + "…(以下省略)"
        st.text_area("本文プレビュー", preview, height=300)

    if len(text) > config.chunking.max_text_chars:
        st.warning(
            f"テキストが長いため、{config.chunking.max_text_chars:,} 文字単位で分割（チャンク処理）して分析します。"
        )

    progress2 = st.progress(0, text="LLMに送信中…")
    progress2.progress(50, text="LLM 解析中…")
    try:
        analyzer = AnalysisServiceCore(
            config=config,
            deepseek_key=deepseek_key,
            gemini_key=gemini_key,
        )
        result = analyzer.analyze(text)
        progress2.progress(100, text="解析完了")
    except LLMAnalysisError as exc:
        st.error(f"⚠️ {exc}")
        st.stop()
    except Exception as exc:
        st.error(f"⚠️ 予期しないエラーが発生しました: {exc}")
        st.stop()

    show_result(result)

    if is_authenticated():
        try:
            result_id = save_extraction_result(
                result=result,
                filename=uploaded_file.name,
                username=st.session_state.get("username"),
            )
            st.info(f"結果を保存しました（ID: {result_id}）。履歴から確認できます。")
        except Exception as exc:
            st.warning(f"結果の保存に失敗しました（処理は継続）: {exc}")

    st.divider()
    st.markdown(
        "<p style='text-align:center;color:var(--color-muted,#64748b);font-size:13px;'>"
        "Powered by DeepSeek / Gemini &nbsp;|&nbsp; "
        "<a href='app_dashboard.py' target='_blank'>📊 ダッシュボードを開く</a>"
        "</p>", unsafe_allow_html=True
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        st.error(f"アプリケーションでエラーが発生しました: {exc}")
        st.code(traceback.format_exc())
