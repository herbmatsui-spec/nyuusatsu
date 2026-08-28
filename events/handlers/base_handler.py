from abc import ABC, abstractmethod
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class BaseEventHandler(ABC):
    """
    イベントハンドラの抽象基底クラス。
    個別のイベント処理ロジックを実装するための基盤を提供する。
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def handle_event(self, event_data: Dict[str, Any]) -> None:
        """
        イベント受信時のエントリーポイント。
        共通の前処理（ログ出力、バリデーション等）を行い、
        実際の処理を `process()` に委譲する。
        """
        try:
            # trace_id があればログコンテキストに付与（後で実装）
            trace_id = event_data.get("trace_id", "unknown")
            self.logger.info(f"Handling event. TraceID: {trace_id}")
            
            self.process(event_data)
            
        except Exception as e:
            self.logger.exception(f"Error processing event: {str(e)}")
            self._handle_failure(event_data, e)

    @abstractmethod
    def process(self, event_data: Dict[Dict[str, Any]]) -> None:
        """
        イベント固有のビジネスロジックをここに実装する。
        """
        pass

    def _handle_failure(self, event_data: Dict[str, Any], exception: Exception) -> None:
        """
        処理失敗時の共通処理。
        後ほどデッドレターキュー (DLQ) への転送ロジックを統合する。
        """
        self.logger.error(f"Event processing failed: {str(exception)}")
        # TODO: Step 8 で DLQ への送信処理を追加
