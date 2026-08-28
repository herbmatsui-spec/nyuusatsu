import logging
import json
from typing import Any, Dict, Optional
from events.publisher import EventPublisher
from events.messaging_config import EventChannels

logger = logging.getLogger(__name__)

class DeadLetterManager:
    """
    処理に失敗したイベントを隔離し、後で再処理可能にするデッドレターキュー (DLQ) 管理クラス。
    """

    def __init__(self, publisher: EventPublisher):
        self.publisher = publisher
        self.dlq_channel = EventChannels.DEAD_LETTER

    def send_to_dlq(self, original_event: Dict[str, Any], error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """
        失敗したイベントをメタデータと共に DLQ チャンネルへ送信する。
        """
        dlq_payload = {
            "original_event": original_event,
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            },
            "context": context or {},
            "retry_count": original_event.get("retry_count", 0) + 1,
            "timestamp": original_event.get("timestamp") # 可能な限り元の時間を保持
        }

        try:
            self.publisher.publish(self.dlq_channel, dlq_payload)
            logger.info(f"Event sent to DLQ: {original_event.get('event_id', 'unknown')}")
        except Exception as e:
            # DLQへの送信自体が失敗した場合は致命的なため、標準ログへ出力
            logger.critical(f"Failed to send event to DLQ! Data loss risk: {e} | Payload: {dlq_payload}")
