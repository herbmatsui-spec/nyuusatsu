# app_dashboard.py に追加するコスト表示ロジック
# 既存の app_dashboard.py は Streamlit で実装されているため、
# Flask の route ではなく Streamlit のページとして実装します。

import streamlit as st
import pandas as pd
import plotly.express as px
from services.cost_manager import CostManager
from datetime import datetime, timedelta, timezone

def render_cost_page():
    st.title("💰 LLM API 利用コスト可視化")
    st.markdown("APIのトークン消費量とリクエスト数の推移を監視します。")
    
    cost_manager = CostManager()
    
    # 今日の統計
    today_usage = cost_manager.get_daily_usage()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("本日消費トークン", f"{today_usage['total_tokens']:,}")
    col2.metric("本日リクエスト数", f"{today_usage['total_requests']:,}")
    col3.metric("日次トークン上限", f"{cost_manager.daily_token_limit:,}")
    
    st.divider()
    
    # 直近30日のデータ収集
    data = []
    for i in range(30, -1, -1):
        date_str = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        usage = cost_manager.get_daily_usage(date_str)
        data.append({
            "date": usage["date"],
            "tokens": usage["total_tokens"],
            "requests": usage["total_requests"]
        })
    
    df = pd.DataFrame(data)
    
    # トークン消費量のグラフ
    fig_tokens = px.line(
        df, x="date", y="tokens", 
        title="日次トークン消費トレンド",
        labels={"date": "日付", "tokens": "トークン数"},
        markers=True
    )
    fig_tokens.update_traces(line_color='#2563eb')
    st.plotly_chart(fig_tokens, use_container_width=True)
    
    # リクエスト数のグラフ
    fig_reqs = px.bar(
        df, x="date", y="requests", 
        title="日次リクエスト数",
        labels={"date": "日付", "requests": "リクエスト数"},
    )
    fig_reqs.update_traces(marker_color='#10b981')
    st.plotly_chart(fig_reqs, use_container_width=True)

    # 詳細テーブル
    with st.expander("詳細データ表示"):
        st.dataframe(df, use_container_width=True, hide_index=True)
