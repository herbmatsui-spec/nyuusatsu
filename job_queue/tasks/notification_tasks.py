import logging
from typing import Any, Dict
from services.notification_service import NotificationService
from services.crawl_service import CrawlService

logger = logging.getLogger(__name__)

def send_notification_task(event_type: str, payload: Dict[str, Any]):
    """
    RQワーカーによって実行される通知タスク。
    イベントタイプに基づいて適切な通知手段（Slack, Email, LINE等）を選択して送信する。
    """
    logger.info(f"Starting notification task for event: {event_type}")
    
    try:
        # 1. 依存サービスの初期化
        # NotificationService は CrawlService を必要とする
        crawl_service = CrawlService()
        notifier = NotificationService(crawl_service=crawl_service)
        
        message = payload.get("message", f"Event {event_type} occurred.")
        
        # 2. イベントタイプに応じた通知処理
        if "crawl.completed" in event_type:
            msg = f"【クロール完了】\n{message}"
            notifier.send_slack_notification(msg)
            
        elif "system.alert" in event_type:
            msg = f"【システムアラート】\n{message}"
            notifier.send_slack_notification(msg)
            # 重大なアラートはメールでも送信
            notifier.send_email_notification(
                subject="System Alert", 
                body=msg, 
                to_email=notifier._get_setting("admin_email", "admin@example.com")
            )
        else:
            # 一般的な通知
            notifier.send_slack_notification(message)

        logger.info(f"Notification sent successfully for {event_type}")
        return {"status": "success", "event_type": event_type}

    except Exception as e:
        logger.exception(f"Notification task failed for {event_type}: {e}")
        raise e
