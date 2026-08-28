import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import plotly.express as px

from config import AppConfig
from utils.auth_decorator import is_authenticated
from utils.session_manager import get_session_manager
from utils.ui import inject_custom_css
from database.session import get_db
from database.models.alert_history import AlertHistory
from database.models.qa_review import QAReview, QAStatusEnum
from services.metrics_query_service import MetricsQueryService
from services.health_checker import HealthChecker

# -----------------------------------------------------------------------------
# Setup Page
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="システム可観測性（Observability）ダッシュボード",
    page_icon="📡",
    layout="wide",
)
inject_custom_css()

# Config & Auth Gate
config = AppConfig()

def show_login_screen() -> bool:
    st.markdown("## 📡 可観測性ダッシュボード 🔐 ログイン")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("ユーザー名")
        password = st.text_input("パスワード", type="password")
        if st.button("ログイン", type="primary"):
            for user in config.auth.allowed_users:
                if user.get("username") == username and user.get("password") == password:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.session_id = get_session_manager(
                        config.auth.session_timeout_minutes
                    ).create_session(username)
                    return True
            st.error("ユーザー名またはパスワードが正しくありません")
    return False

# 認証チェック
if config.auth.enable_auth and not is_authenticated():
    if show_login_screen():
        st.rerun()
    st.stop()

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
st.markdown(
    "<div class='lp-hero'><h1>📡 システム可観測性（Observability）ダッシュボード</h1>"
    "<p>リアルタイムでパイプラインの状態・メトリクス・ログ・アラートを可視化します。</p></div>",
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.header("⚙️ 設定・管理")
    if is_authenticated():
        st.write(f"ログインユーザー: **{st.session_state.get('username', 'unknown')}**")
    
    st.divider()
    time_window = st.selectbox(
        "データ表示期間",
        ["直近 24時間", "直近 3日間", "直近 7日間"],
        index=0
    )
    
    hours_map = {"直近 24時間": 24, "直近 3日間": 72, "直近 7日間": 168}
    hours = hours_map[time_window]
    
    st.divider()
    if st.button("🔄 画面更新", use_container_width=True):
        st.rerun()

    if config.auth.enable_auth:
        if st.button("🔓 ログアウト", use_container_width=True):
            sid = st.session_state.get("session_id")
            if sid:
                get_session_manager().logout(sid)
            for key in ("authenticated", "username", "session_id"):
                st.session_state.pop(key, None)
            st.rerun()

# -----------------------------------------------------------------------------
# Main Dashboard Sections
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📊 パイプライン監視", "📝 構造化ログビューア", "🚨 アラート履歴", "🛠 QA 進捗"])

with tab1:
    # 1. 統合ヘルスステータス
    st.subheader("🏥 稼働ヘルスステータス")
    checker = HealthChecker()
    health_data = checker.check_all()
    
    status_emoji = {"healthy": "✅ HEALTHY", "degraded": "⚠️ DEGRADED", "unhealthy": "🚨 UNHEALTHY"}
    st.markdown(f"**全体ステータス**: {status_emoji.get(health_data['overall_status'], '❓ UNKNOWN')}")
    
    cols = st.columns(len(health_data["components"]))
    for col, (comp_name, comp_info) in zip(cols, health_data["components"].items()):
        status = comp_info["status"]
        if status == "healthy":
            col.success(f"**{comp_name}**\n\n正常稼働中")
        elif status == "degraded":
            col.warning(f"**{comp_name}**\n\n警告\n\n{comp_info['message']}")
        else:
            col.error(f"**{comp_name}**\n\n停止中 / エラー\n\n{comp_info['message']}")

    st.divider()

    # 2. パイプライン スループットと処理時間
    st.subheader("📈 パイプライン処理統計")
    query_service = MetricsQueryService()
    summary = query_service.get_pipeline_summary(hours=hours)
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric(
            label="🔍 クロール処理件数 (成功/総数)", 
            value=f"{summary['crawl']['success']} / {summary['crawl']['total']}",
            delta=f"平均時間: {summary['crawl']['duration_avg_ms']} ms"
        )
    with kpi2:
        st.metric(
            label="📥 PDFダウンロード数 (成功/総数)", 
            value=f"{summary['download']['success']} / {summary['download']['total']}",
            delta=f"平均時間: {summary['download']['duration_avg_ms']} ms"
        )
    with kpi3:
        st.metric(
            label="🧠 LLM解析数 (成功/総数)", 
            value=f"{summary['analysis']['success']} / {summary['analysis']['total']}",
            delta=f"平均時間: {summary['analysis']['duration_avg_ms']} ms"
        )
    with kpi4:
        st.metric(
            label="⚙️ バックグラウンドタスク (成功/総数)", 
            value=f"{summary['task_queue']['success']} / {summary['task_queue']['total']}",
            delta=f"平均時間: {summary['task_queue']['duration_avg_ms']} ms"
        )

    st.divider()

    # 3. エラー分布チャート
    st.subheader("⚠️ エラー分布 (ステージ別・エラータイプ別)")
    errors = query_service.get_error_distribution(hours=hours)
    if errors:
        df_errors = pd.DataFrame(errors)
        fig = px.bar(
            df_errors, 
            x="stage", 
            y="count", 
            color="error_type", 
            title="エラー発生内訳",
            labels={"stage": "パイプラインステージ", "count": "発生件数", "error_type": "エラー種別"},
            barmode="group"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("指定された期間内にエラーメトリクスは記録されていません。")

with tab2:
    st.subheader("🔍 構造化ログリーダー (logs/app.log)")
    log_file_path = "logs/app.log"
    
    if os.path.exists(log_file_path):
        # フィルター設定
        log_col1, log_col2, log_col3 = st.columns(3)
        with log_col1:
            level_filter = st.multiselect("ログレベル", ["INFO", "WARNING", "ERROR"], default=["WARNING", "ERROR"])
        with log_col2:
            stage_filter = st.multiselect("ステージ", ["crawl", "download", "analysis", "notification", "task_queue"])
        with log_col3:
            trace_id_search = st.text_input("Trace ID で検索")
            
        logs_list = []
        with open(log_file_path, "r", encoding="utf-8") as f:
            # 負荷低減のため後ろから読み取る
            lines = f.readlines()
            for line in reversed(lines):
                if len(logs_list) >= 200:  # 最大200件
                    break
                try:
                    log_data = json.loads(line)
                    # フィルター適用
                    if level_filter and log_data.get("level") not in level_filter:
                        continue
                    if stage_filter and log_data.get("pipeline_stage") not in stage_filter:
                        continue
                    if trace_id_search and trace_id_search not in log_data.get("trace_id", ""):
                        continue
                    logs_list.append(log_data)
                except (json.JSONDecodeError, ValueError):
                    # 非構造化テキストログの場合
                    if not level_filter and not stage_filter and not trace_id_search:
                        logs_list.append({"message": line.strip()})
        
        if logs_list:
            df_logs = pd.DataFrame(logs_list)
            st.dataframe(df_logs, use_container_width=True)
        else:
            st.info("条件に一致するログは見つかりませんでした。")
    else:
        st.warning(f"ログファイルが見つかりません: {log_file_path}")

with tab3:
    st.subheader("🚨 警告・アラート履歴")
    
    with get_db() as session:
        alerts = session.query(AlertHistory).order_by(AlertHistory.timestamp.desc()).all()
        
    if alerts:
        alert_records = []
        for a in alerts:
            alert_records.append({
                "発生日時": a.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                "監視対象": a.component,
                "重要度": a.severity,
                "内容": a.message,
                "復旧日時": a.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if a.resolved_at else "⚠️ 未復旧"
            })
            
        df_alerts = pd.DataFrame(alert_records)
        
        # 未復旧のものをハイライト表示
        def highlight_unresolved(row):
            return ['background-color: #ffcccc' if row['復旧日時'] == "⚠️ 未復旧" else '' for _ in row]
            
        st.dataframe(df_alerts.style.apply(highlight_unresolved, axis=1), use_container_width=True)
    else:
        st.info("現在アラート履歴はありません。システムは安定稼働しています。")
        # QA 進捗タブ
        with tab4:
            st.subheader("🛠 QA 進捗")
            with get_db() as qa_session:
                pending = qa_session.query(QAReview).filter(QAReview.status == QAStatusEnum.PENDING).count()
                reviewing = qa_session.query(QAReview).filter(QAReview.status == QAStatusEnum.REVIEWING).count()
                approved = qa_session.query(QAReview).filter(QAReview.status == QAStatusEnum.APPROVED).count()
                rejected = qa_session.query(QAReview).filter(QAReview.status == QAStatusEnum.REJECTED).count()
                data = {
                    "ステータス": ["保留", "レビュー中", "承認", "却下"],
                    "件数": [pending, reviewing, approved, rejected]
                }
                df = pd.DataFrame(data)
                st.table(df)
