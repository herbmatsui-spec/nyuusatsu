import os
import logging
import requests
from abc import ABC, abstractmethod
from dotenv import load_dotenv

load_dotenv()

class NotificationService(ABC):
    """Abstract base class for notification services."""
    @abstractmethod
    def send(self, message: str):
        pass

class LineNotificationService(NotificationService):
    """LINE Messaging API notification service
    """
    def __init__(self):
        self.access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        self.user_id = os.getenv("LINE_USER_ID")
        self.api_url = "https://api.line.me/v2/bot/message/push"

    def send(self, message: str):
        if not self.access_token or not self.user_id:
            logging.error("LINE API credentials missing in .env")
            return False
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        payload = {
            "to": self.user_id,
            "messages": [{"type": "text", "text": message}]
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logging.error(f"Failed to send LINE notification: {e}")
            return False

class SlackNotificationService(NotificationService):
    """Slack Webhook notification service
    """
    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    def send(self, message: str):
        if not self.webhook_url:
            logging.error("Slack Webhook URL missing in .env")
            return False
        
        payload = {"text": message}
        
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logging.error(f"Failed to send Slack notification: {e}")
            return False

def create_notification_service(notify_type: str) -> NotificationService:
    """Factory function to create a notification service
    """
    if notify_type.lower() == "line":
        return LineNotificationService()
    elif notify_type.lower() == "slack":
        return SlackNotificationService()
    else:
        raise ValueError(f"Unsupported notification type: {notify_type}")

def format_new_bid_message(bids: list) -> str:
    """新着入札案件の一覧を通知用テキストに整形する。"""
    if not bids:
        return "新着の入札案件はありません。"
    lines = ["【新着入札案件】"]
    for bid in bids:
        name = getattr(bid, "project_name", None) or bid.get("project_name", "") if isinstance(bid, dict) else str(bid)
        org = getattr(bid, "organization", None) or (bid.get("organization", "") if isinstance(bid, dict) else "")
        budget = getattr(bid, "budget", None) or (bid.get("budget", "") if isinstance(bid, dict) else "")
        line = f"- {name}"
        if org:
            line += f"（{org}）"
        if budget:
            line += f" 予算: {budget}"
        lines.append(line)
    return "\n".join(lines)


def notify_quality_issue(metric_name: str, value: float, level: str = "warn") -> bool:
    """品質メトリクスの警告またはアラートを通知する。
    level: "warn" (警告) または "alert" (重大)"""
    message = f"⚠️ 【品質{'警告' if level == 'warn' else 'アラート'}】\nメトリクス: {metric_name}\n値: {value}"
    # Slack が設定されていれば優先的に利用、次に LINE
    for notify_type in ("slack", "line"):
        try:
            service = create_notification_service(notify_type)
            if service.send(message):
                return True
        except Exception as e:
            logging.error(f"{notify_type} 通知失敗: {e}")
    return False
    """Formats a list of new bids into a readable message
    """
    if not bids:
        return "新規案件は見つかりませんでした。"
    
    message = "🔔 【新着案件通知】\n"
    message += f"合計 {len(bids)} 件の新規案件を検出しました。\n\n"
    
    for i, bid in enumerate(bids, 1):
        title = bid.get('title', '無題')
        url = bid.get('url', '#')
        message += f"{i}. {title}\n{url}\n\n"
    
    return message
