"""
Competitor Alert Service
特定競合が入札・落札した際にアラート条件を判定し通知する。
"""
import logging
from typing import Any, Dict, Optional

from services.alert_manager import AlertManager

logger = logging.getLogger(__name__)


class CompetitorAlertService:
    """
    以下の条件を満たす場合にアラート発報:
      - 落札企業が「is_target_company=True」の競合である
      - 業種カテゴリがユーザーが関心のあるカテゴリと一致する
      - (optional) 予定価格が指定下限を超える
    """

    TARGET_CATEGORIES = {"建設": True, "IT": True, "コンサル": True}

    def __init__(self, min_budget: int = 0):
        self.min_budget = min_budget
        self.alert_manager = AlertManager()

    def should_alert(self, award_data: Dict[str, Any], competitor: Any) -> bool:
        """アラートを発報すべきか判定する。"""
        if not competitor:
            return False
        if not competitor.get("is_target_company"):
            return False
        category = competitor.get("industry_category")
        if category and category not in self.TARGET_CATEGORIES:
            return False
        budget = award_data.get("budget_amount") or 0
        if self.min_budget > 0 and budget < self.min_budget:
            return False
        return True

    def send_alert(self, award_data: Dict[str, Any], competitor: Dict[str, Any]) -> None:
        """アラートを発報する。"""
        company = competitor.get("normalized_name", "不明")
        project = award_data.get("project_name") or award_data.get("source_url", "不明")
        budget = award_data.get("budget_amount") or 0
        contract = award_data.get("contract_amount") or 0
        rate = award_data.get("award_rate") or 0.0
        agency = award_data.get("agency_name") or "不明"

        message = (
            f"🏢 競合出現アラート\n"
            f"企業: {company}\n"
            f"案件: {project}\n"
            f"予定価格: {budget:,}円\n"
            f"落札価格: {contract:,}円（落札率 {rate}%）\n"
            f"発注機関: {agency}\n"
            f"公告日: {award_data.get('announcement_date')}"
        )
        try:
            self.alert_manager.evaluate_and_alert(
                component=f"Competitor:{company}",
                is_healthy=True,
                error_message=message,
            )
            logger.info(f"Sent competitor alert for {company}")
        except Exception as e:
            logger.error(f"Failed to send competitor alert: {e}")
