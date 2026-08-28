from abc import ABC, abstractmethod
from typing import Any, Dict

class EventPublisher(ABC):
    """
    イベント発行者の抽象基底クラス。
    具体的な実装（Redis, RabbitMQ, Kafkaなど）に関わらず、
    アプリケーションコードから一貫した方法でイベントを送信できるようにする。
    """

    @abstractmethod
    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        指定されたイベントタイプとペイロードをメッセージブローカーに送信する。
        
        Args:
            event_type (str): 送信するイベントの識別子 (例: 'crawl.requested')
            payload (Dict[str, Any]): イベントに付随するデータ
        """
        pass
