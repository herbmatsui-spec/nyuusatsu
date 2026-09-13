import logging
from typing import Any, Dict, Optional
from database.session import get_db
from services.bid_analysis_service import BidAnalysisService
from events.publisher import EventPublisher
from events.redis_publisher import RedisPublisher
from events.schemas import TextExtracted, AnalysisFailed
from events.serializer import EventSerializer

logger = logging.getLogger(__name__)

def extract_text_task(bid_id: int, pdf_path: str, run_id: str):
    """
    PDFからテキストを抽出する独立タスク。
    抽出完了後、TextExtracted イベントを発行する。
    """
    logger.info(f"Starting OCR/Text Extraction task for bid {bid_id} (run: {run_id})")
    
    # Publisherの初期化 (RedisPublisher)
    publisher = RedisPublisher()
    
    try:
        with get_db() as session:
            # 1. 分析サービスの初期化
            analysis_service = BidAnalysisService(session)
            
            # 2. テキスト抽出実行
            # extract_text_from_pdf は内部で pdfplumber -> OCR フォールバックを制御している
            text = analysis_service.extract_text_from_pdf(pdf_path)
            
            # 3. 成功イベントの発行
            # 抽出手法の判定 (簡易的に文字数やログから判定せず、今回は metadata として送る)
            event = TextExtracted(
                trace_id=run_id,
                payload={
                    "bid_id": bid_id,
                    "text": text,
                    "pdf_path": pdf_path,
                    "run_id": run_id
                }
            )
            publisher.publish("event.text.extracted", event.model_dump())
            logger.info(f"Published TextExtracted event for bid {bid_id}")

    except Exception as e:
        logger.exception(f"Text extraction failed for bid {bid_id}: {str(e)}")
        
        # 失敗イベントの発行
        error_event = AnalysisFailed(
            trace_id=run_id,
            payload={
                "bid_id": bid_id,
                "error": str(e),
                "stage": "extraction",
                "run_id": run_id
            }
        )
        publisher.publish("event.analysis.failed", error_event.model_dump())
        raise e
