import logging
from typing import Any, Dict
from events.handlers.base_handler import BaseEventHandler
from events.schemas import BaseEvent
from queue.enqueue import TaskEnqueueFacade
from services.pipeline_state_service import PipelineStateService

logger = logging.getLogger(__name__)

class AnalysisCompletedHandler(BaseEventHandler):
    """
    LLM分析完了イベントを処理し、通知タスクを投入し、パイプライン状態を更新する
    """
    def __init__(self, enqueue_facade: TaskEnqueueFacade, state_service: PipelineStateService):
        super().__init__()
        self.enqueue_facade = enqueue_facade
        self.state_service = state_service

    def handle(self, event_data: Dict[str, Any]):
        """
        AnalysisCompleted イベントの処理
        event_data payload: {
            "run_id": str,
            "bid_id": int,
            "analysis_result": dict
        }
        """
        try:
            payload = event_data.get("payload", {})
            run_id = payload.get("run_id")
            bid_id = payload.get("bid_id")
            analysis_result = payload.get("analysis_result", {})

            if not run_id or not bid_id:
                logger.error("Event payload missing run_id or bid_id")
                return

            logger.info(f"Handling AnalysisCompleted for run {run_id}, bid {bid_id}")

            # 1. 通知タスクの投入
            # 解析結果に基づいた通知内容を構成してキューに投入
            notification_payload = {
                "bid_id": bid_id,
                "run_id": run_id,
                "summary": analysis_result.get("summary", "解析完了"),
                "budget": analysis_result.get("budget", "記載なし")
            }
            
            self.enqueue_facade.enqueue_notification(
                event_type="BID_ANALYSIS_COMPLETED",
                payload=notification_payload
            )

            # 2. パイプライン進捗の更新
            # 処理完了数をインクリメント
            # 注: PipelineStateService に increment_processed メソッドを追加することを推奨
            # 現状は get_run して更新する
            from database.session import get_db
            with get_db() as session:
                from database.models import PipelineRun
                run = session.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
                if run:
                    run.processed_items += 1
                    # 全件処理が完了したかチェック (簡易的に)
                    if run.total_items > 0 and run.processed_items >= run.total_items:
                        run.status = "COMPLETED"
                        from datetime import datetime
                        run.completed_at = datetime.utcnow()
                    session.commit()

        except Exception as e:
            logger.exception(f"Error in AnalysisCompletedHandler: {str(e)}")
            run_id = event_data.get("payload", {}).get("run_id")
            if run_id:
                self.state_service.update_status(run_id, "FAILED", error_message=str(e))
            raise e
