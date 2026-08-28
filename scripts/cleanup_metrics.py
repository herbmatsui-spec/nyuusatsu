import sys
import os
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import get_db
from database.models.pipeline_metric import PipelineMetric

logger = logging.getLogger("cleanup_metrics")

def cleanup_old_metrics(retention_days: int = 30):
    """
    指定された保持期間を超えた古いパイプラインメトリクスデータをDBから削除する。
    """
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    logger.info(f"Starting metrics cleanup. Removing records older than {cutoff} (retention: {retention_days} days)")
    
    try:
        with get_db() as session:
            deleted_count = session.query(PipelineMetric).filter(
                PipelineMetric.timestamp < cutoff
            ).delete()
            session.commit()
            logger.info(f"Successfully deleted {deleted_count} old metric records.")
            return deleted_count
    except Exception as e:
        logger.error(f"Failed to cleanup old metrics: {e}", exc_info=True)
        return 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    cleanup_old_metrics(30)
