from flask import Blueprint, render_template, jsonify
from services.cost_manager import CostManager
from datetime import datetime, timedelta

cost_bp = Blueprint('cost_dashboard', __name__)

@cost_bp.route('/cost-dashboard')
def render_dashboard():
    return render_template('cost_dashboard.html')

@cost_bp.route('/api/cost/usage')
def get_usage_data():
    cost_manager = CostManager()
    data = []
    # 直近30日のデータを取得
    for i in range(30, -1, -1):
        date_str = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        usage = cost_manager.get_daily_usage(date_str)
        data.append({
            "date": usage["date"],
            "tokens": usage["total_tokens"],
            "requests": usage["total_requests"]
        })
    return jsonify(data)
