import logging
from typing import Any, Dict
from events.handlers.base_handler import BaseEventHandler
from events.schemas import BaseEvent
from events.serializer import EventSerializer
from queue.enqueue import TaskEnqueueFacade
from services.pipeline_state_service import PipelineStateService

logger = logging.getLogger(__name__)

class CrawlCompletedHandler(BaseEventHandler):
    """
    クロール完了イベントを処理し、検出された各入札に対してPDFダウンロードタスクを投入する
    """
    def __init__(self, enqueue_facade: TaskEnqueueFacade, state_service: PipelineStateService):
        super().__init__()
        self.enqueue_facade = enqueue_facade
        self.state_service = state_service

    def handle(self, event_data: Dict[str, Any]):
        """
        CrawlCompleted イベントの処理
        event_data payload: {
            "run_id": str,
            "agency_id": int,
            "bids": [
                {"bid_id": int, "url": str, "title": str},
                ...
            ]
        }
        """
        try:
            # 1. イベントの検証 (スキーマチェック)
            # 注: 現時点の schemas.py に CrawlCompleted がないため payload から直接取得
            # 将来的には schemas.py に CrawlCompleted を追加すべき
            payload = event_data.get("payload", {})
            run_id = payload.get("run_id")
            agency_id = payload.get("agency_id")
            bids = payload.get("bids", [])

            if not run_id:
                logger.error("Event payload missing run_id")
                return

            logger.info(f"Handling CrawlCompleted for run {run_id}, found {len(bids)} bids")

            # 2. パイプライン状態の更新 (総件数の記録)
            self.state_service.update_progress(
                run_id=run_id, 
                total=len(bids)
            )

            # 3. 各入札に対してPDF処理タスクをキューに投入
            for bid in bids:
                bid_id = bid.get("bid_id")
                url = bid.get("url")
                
                if bid_id and url:
                    # PDF処理タスクを投入 (Phase 2 で実装した facade を利用)
                    self.enqueue_facade.enqueue_pdf_download(
                        bid_id=bid_id,
                        url=url,
                        agency_id=agency_id,
                        run_id=run_id # trace_idとして伝搬
                    )
                else:
                    logger.warning(f"Skipping bid due to missing info: {bid}")

            # 4. ステータスを RUNNING に更新 (最初のタスクが投入されたため)
            self.state_service.update_status(run_id, "RUNNING")

        except Exception as e:
            logger.exception(f"Error in CrawlCompletedHandler: {str(e)}")
            # 必要に応じて pipeline_state_service を通じてエラーを記録
            run_id = event_data.get("payload", {}).get("run_id")
            if run_id:
                self.state_service.update_status(run_id, "FAILED", error_message=str(e))
            raise e
