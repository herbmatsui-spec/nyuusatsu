import logging
from typing import Any, Dict, Optional, Union
from queue.queues import crawl_queue, pdf_queue, analysis_queue, notification_queue
from queue.rq_config import rq_config

logger = logging.getLogger(__name__)

class TaskEnqueueFacade:
    """
    アプリケーションからRQタスクを簡単に投入するためのファサード。
    直接 Queue オブジェクトを操作せず、このインターフェースを通じることで
    将来的なキュー名の変更や優先度の調整を一箇所で管理できる。
    """

    @staticmethod
    def enqueue_crawl(agency_id: int, priority: str = "default"):
        """クロールタスクを投入"""
        from queue.tasks.crawl_tasks import crawl_agency_task
        job = crawl_queue.enqueue(
            crawl_agency_task, 
            args=(agency_id,), 
            job_id=f"crawl:agency:{agency_id}"
        )
        logger.info(f"Enqueued crawl task for agency {agency_id}. JobID: {job.id}")
        return job

    @staticmethod
    def enqueue_pdf_process(bid_url: str, agency_id: int):
        """PDFダウンロードおよび抽出タスクを投入"""
        from queue.tasks.pdf_tasks import download_and_extract_task
        # URLをハッシュ化してユニークなジョブIDを作成
        import hashlib
        url_hash = hashlib.md5(bid_url.encode()).hexdigest()
        job = pdf_queue.enqueue(
            download_and_extract_task, 
            args=(bid_url, agency_id), 
            job_id=f"pdf:{url_hash}"
        )
        logger.info(f"Enqueued PDF process task for {bid_url}. JobID: {job.id}")
        return job

    @staticmethod
    def enqueue_analysis(bid_id: int):
        """分析タスクを投入"""
        from queue.tasks.analysis_tasks import analyze_bid_task
        job = analysis_queue.enqueue(
            analyze_bid_task, 
            args=(bid_id,), 
            job_id=f"analysis:bid:{bid_id}"
        )
        logger.info(f"Enqueued analysis task for bid {bid_id}. JobID: {job.id}")
        return job

    @staticmethod
    def enqueue_notification(event_type: str, payload: Dict[str, Any]):
        """通知タスクを投入"""
        from queue.tasks.notification_tasks import send_notification_task
        job = notification_queue.enqueue(
            send_notification_task, 
            args=(event_type, payload)
        )
        logger.info(f"Enqueued notification task for {event_type}. JobID: {job.id}")
        return job

# 簡易利用のための関数エクスポート
def enqueue_crawl(agency_id: int):
    return TaskEnqueueFacade.enqueue_crawl(agency_id)

def enqueue_pdf_process(bid_url: str, agency_id: int):
    return TaskEnqueueFacade.enqueue_pdf_process(bid_url, agency_id)

def enqueue_analysis(bid_id: int):
    return TaskEnqueueFacade.enqueue_analysis(bid_id)

def enqueue_notification(event_type: str, payload: Dict[str, Any]):
    return TaskEnqueueFacade.enqueue_notification(event_type, payload)
