from flask import Blueprint
from services.cost_dashboard_blueprint import cost_bp

def register_blueprints(app):
    app.register_blueprint(cost_bp)
    # ここに今後他のブループリントを追加
    # from app.blueprints.crawl_history import history_bp
    # app.register_blueprint(history_bp)
