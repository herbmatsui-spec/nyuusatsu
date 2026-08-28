import logging
import warnings
from typing import List, Optional
from database.session import get_db
from services.pipeline_state_service import PipelineStateService
from queue.enqueue import TaskEnqueueFacade
from events.redis_publisher import RedisPublisher

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    """
    非同期パイプラインの新しいエントリポイント。
    直列的な pipeline_service.py に代わり、タスク投入とイベント連鎖を開始させる。
    """
    def __init__(self, state_service: PipelineStateService, enqueue_facade: TaskEnqueueFacade):
        self.state_service = state_service
        self.enqueue_facade = enqueue_facade
        self.publisher = RedisPublisher()

    def start_pipeline(self, agency_id: int, agency_name: Optional[str] = None):
        """
        パイプラインを開始し、最初のクロールタスクを投入する。
        """
        try:
            logger.info(f"Starting async pipeline for agency {agency_id}")
            
            # 1. パイプライン状態レコードの作成 (trace_id/run_id の発行)
            run_id = self.state_service.create_run(
                agency_id=agency_id, 
                agency_name=agency_name
            )
            
            # 2. 最初のクロールタスクを投入
            # 注: 現状の enqueue_crawl は run_id を受け取らないため、
            # 本来は enqueue_crawl のシグネチャを拡張し run_id を渡すべき。
            # ここではまずタスクを投入し、その後のイベント連鎖で run_id を伝搬させる。
            self.enqueue_facade.enqueue_crawl(agency_id=agency_id)
            
            # 3. クロール開始イベントを発行 (オプション)
            self.publisher.publish("event.crawl.started", {
                "run_id": run_id,
                "agency_id": agency_id,
                "timestamp": "..." # serializer で処理される
            })
            
            logger.info(f"Pipeline successfully initiated. RunID: {run_id}")
            return run_id

        except Exception as e:
            logger.exception(f"Failed to start pipeline for agency {agency_id}: {str(e)}")
            raise e

    def get_pipeline_status(self, run_id: str):
        """
        特定のパイプライン実行の現在のステータスを返す
        """
        return self.state_service.get_run(run_id)
