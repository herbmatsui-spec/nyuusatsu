import logging
from typing import Any, Dict
from events.handlers.base_handler import BaseEventHandler
from events.schemas import BaseEvent
from queue.enqueue import TaskEnqueueFacade
from services.pipeline_state_service import PipelineStateService

logger = logging.getLogger(__name__)

class OCRCompletedHandler(BaseEventHandler):
    """
    テキスト抽出完了イベントを処理し、LLM分析タスクを投入する
    """
    def __init__(self, enqueue_facade: TaskEnqueueFacade, state_service: PipelineStateService):
        super().__init__()
        self.enqueue_facade = enqueue_facade
        self.state_service = state_service

    def handle(self, event_data: Dict[str, Any]):
        """
        TextExtracted イベントの処理
        event_data payload: {
            "run_id": str,
            "bid_id": int,
            "text": str,
            "pdf_path": str
        }
        """
        try:
            payload = event_data.get("payload", {})
            run_id = payload.get("run_id")
            bid_id = payload.get("bid_id")
            text = payload.get("text")

            if not run_id or not bid_id or not text:
                logger.error("Event payload missing run_id, bid_id or text")
                return

            logger.info(f"Handling TextExtracted for run {run_id}, bid {bid_id}")

            # 次のステップであるLLM分析タスクを投入
            # 抽出したテキストは DB に保存済みか、または分析タスク内で処理される想定
            self.enqueue_facade.enqueue_analysis(
                bid_id=bid_id
            )

        except Exception as e:
            logger.exception(f"Error in OCRCompletedHandler: {str(e)}")
            run_id = event_data.get("payload", {}).get("run_id")
            if run_id:
                self.state_service.update_status(run_id, "FAILED", error_message=str(e))
            raise e
