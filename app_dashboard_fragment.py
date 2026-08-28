# 改善点2 ステップ32-34: app_dashboard.py および templates/cost_dashboard.html
# LLM APIのコスト消費量を可視化するダッシュボードを実装します。

import os
import logging
from flask import Flask, render_template, jsonify, request
from database.session import SessionLocal
from services.bid_service import BidService
from database.repositories.bid_repository import BidRepository
from services.cost_manager import CostManager

# ... (既存のインポート)

app = Flask(__name__)
cost_manager = CostManager()

@app.route('/api/cost/usage')
def get_cost_usage():
    """
    過去30日間の日次トークン消費量を返すAPIエンドポイント。
    """
    try:
        from datetime import datetime, timedelta
        data = []
        for i in range(30, -1, -1):
            date_str = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            usage = cost_manager.get_daily_usage(date_str)
            data.append({
                "date": usage["date"],
                "tokens": usage["total_tokens"],
                "requests": usage["total_requests"]
            })
        return jsonify(data)
    except Exception as e:
        logging.error(f"Error fetching cost usage: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/cost-dashboard')
def cost_dashboard():
    """
    コストダッシュボード画面を表示する。
    """
    return render_template('cost_dashboard.html')

# ... (残りのルート定義)
