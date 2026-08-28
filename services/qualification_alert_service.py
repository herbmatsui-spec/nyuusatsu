"""
Qualification Alert Service
資格マッチ通知を担当するサービス。
"""
import logging
from typing import Any, Dict

from services.alert_manager import AlertManager

logger = logging.getLogger(__name__)


class QualificationAlertService:
    def __init__(self):
        self.alert_manager = AlertManager()
        self.target_categories = {"建設", "IT", "コンサル", "物品", "委託"}

    def should_alert(self, match_result: Dict[str, Any]) -> bool:
        if not match_result.get("can_apply"):
            return False
        return True

    def send_alert(self, match_result: Dict[str, Any], bid_info: Dict[str, Any]) -> None:
        if not self.should_alert(match_result):
            return

        grade = match_result.get("company_grade", "不明")
        project = bid_info.get("project_name") or bid_info.get("filename", "不明")
        agency = bid_info.get("organization_name") or "不明"

        message = (
            f"🎯 応募可能案件追加\n"
            f"案件: {project}\n"
            f"発注機関: {agency}\n"
            f"自社等級: {grade}\n"
            f"マッチレベル: {match_result.get('match_level', 'unknown')}\n"
            f"スコア: {match_result.get('score', 0)} / 1.0"
        )
        try:
            self.alert_manager.evaluate_and_alert(
                component="QualificationMatch",
                is_healthy=False,
                error_message=message,
            )
            logger.info(f"Sent qualification match alert: {project}")
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")