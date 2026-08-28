import uuid
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from database.models import PipelineRun
from database.session import get_db

logger = logging.getLogger(__name__)

class PipelineStateService:
    """
    非同期パイプラインの実行状態を管理するサービス
    """
    
    def create_run(self, agency_id: Optional[int] = None, agency_name: Optional[str] = None) -> str:
        """
        新しいパイプライン実行レコードを作成し、run_id (trace_id) を返す
        """
        run_id = str(uuid.uuid4())
        with get_db() as session:
            new_run = PipelineRun(
                run_id=run_id,
                agency_id=agency_id,
                agency_name=agency_name,
                status="PENDING"
            )
            session.add(new_run)
            session.commit()
            logger.info(f"Created pipeline run {run_id} for agency {agency_id}")
        return run_id

    def update_status(self, run_id: str, status: str, error_message: Optional[str] = None):
        """
        パイプラインのステータスを更新する
        """
        with get_db() as session:
            run = session.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
            if run:
                run.status = status
                if error_message:
                    run.error_message = error_message
                if status == "COMPLETED" or status == "FAILED":
                    run.completed_at = datetime.utcnow()
                session.commit()
                logger.info(f"Updated pipeline run {run_id} status to {status}")
            else:
                logger.error(f"Pipeline run {run_id} not found for status update")

    def update_progress(self, run_id: str, total: Optional[int] = None, processed: Optional[int] = None, failed: Optional[int] = None):
        """
        処理件数の進捗を更新する
        """
        with get_db() as session:
            run = session.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
            if run:
                if total is not None:
                    run.total_items = total
                if processed is not None:
                    run.processed_items = processed
                if failed is not None:
                    run.failed_items = failed
                session.commit()
            else:
                logger.error(f"Pipeline run {run_id} not found for progress update")

    def get_run(self, run_id: str) -> Optional[PipelineRun]:
        """
        特定の実行状態を取得する
        """
        with get_db() as session:
            return session.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()

    def get_recent_runs(self, limit: int = 10) -> List[PipelineRun]:
        """
        最近の実行履歴を取得する
        """
        with get_db() as session:
            return session.query(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(limit).all()
