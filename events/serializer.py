import json
import logging
from typing import Any, Dict, Optional, Union
from events.schemas import BaseEvent

logger = logging.getLogger(__name__)

class EventSerializer:
    """
    イベントモデルとJSON文字列の間の変換を管理するシリアライザ。
    Pydanticモデルによるバリデーションと、汎用的なDict形式の相互変換を行う。
    """

    @staticmethod
    def serialize(event: Union[BaseEvent, Dict[str, Any]]) -> str:
        """
        イベントオブジェクトをJSON文字列に変換する。
        """
        try:
            if isinstance(event, BaseEvent):
                # Pydanticモデルの場合は model_dump() (v2) または dict() (v1) を使用
                data = event.model_dump() if hasattr(event, "model_dump") else event.dict()
                # datetime などを文字列に変換するために default=str を指定
                return json.dumps(data, default=str, ensure_ascii=False)
            
            return json.dumps(event, default=str, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Serialization failed: {e}")
            raise

    @staticmethod
    def deserialize(data: str, event_class: Optional[Any] = None) -> Union[BaseEvent, Dict[str, Any]]:
        """
        JSON文字列をイベントオブジェクトまたは辞書に変換する。
        event_class が指定された場合は、そのクラスでバリデーションを行う。
        """
        try:
            payload = json.loads(data)
            if event_class:
                return event_class(**payload)
            return payload
        except Exception as e:
            logger.error(f"Deserialization failed: {e}")
            raise
