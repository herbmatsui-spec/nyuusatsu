import logging
from typing import Any, Dict
from events.handlers.base_handler import BaseEventHandler
from events.schemas import BaseEvent
from queue.enqueue import TaskEnqueueFacade
from services.pipeline_state_service import PipelineStateService

logger = logging.getLogger(__name__)

class PDFDownloadedHandler(BaseEventHandler):
    """
    PDFダウンロード完了イベントを処理し、テキスト抽出・分析タスクを投入する
    """
    def __init__(self, enqueue_facade: TaskEnqueueFacade, state_service: PipelineStateService):
        super().__init__()
        self.enqueue_facade = enqueue_facade
        self.state_service = state_service

    def handle(self, event_data: Dict[str, Any]):
        """
        PDFDownloaded イベントの処理
        event_data payload: {
            "run_id": str,
            "bid_id": int,
            "pdf_path": str,
            "url": str
        }
        """
        try:
            payload = event_data.get("payload", {})
            run_id = payload.get("run_id")
            bid_id = payload.get("bid_id")
            pdf_path = payload.get("pdf_path")

            if not run_id or not bid_id:
                logger.error("Event payload missing run_id or bid_id")
                return

            logger.info(f"Handling PDFDownloaded for run {run_id}, bid {bid_id}")

            # 次のステップである分析タスク (OCR含む) を投入
            # 現時点の enqueue_analysis は bid_id のみを受け取るため、
            # 現状の facade に合わせて呼び出す。
            self.enqueue_facade.enqueue_analysis(
                bid_id=bid_id
            )

        except Exception as e:
            logger.exception(f"Error in PDFDownloadedHandler: {str(e)}")
            run_id = event_data.get("payload", {}).get("run_id")
            if run_id:
                self.state_service.update_status(run_id, "FAILED", error_message=str(e))
            raise e
