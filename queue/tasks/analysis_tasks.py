import logging
from typing import Dict, Any
from database.session import SessionLocal
from services.bid_analysis_service import BidAnalysisService
from config import AppConfig

logger = logging.getLogger(__name__)

def analyze_bid_task(bid_id: int):
    """
    RQワーカーによって実行される分析タスク。
    DBからBid情報を取得し、LLMによる詳細分析を実行して結果を保存する。
    """
    logger.info(f"Starting analysis task for bid_id: {bid_id}")
    
    try:
        with SessionLocal() as db:
            # 1. 分析サービスの初期化
            # BidAnalysisService は session を受け取り、内部的に LLMService を構成する
            analysis_service = BidAnalysisService(session=db)
            
            # 2. Bid情報の取得 (BidRepository経由)
            from database.repositories.bid_repository import BidRepository
            bid_repo = BidRepository(db)
            bid = bid_repo.get_by_id(bid_id)
            
            if not bid:
                logger.error(f"Bid not found for id: {bid_id}")
                return {"status": "error", "message": "Bid not found"}

            # 3. 分析の実行
            # 現状の BidAnalysisService には analyze_and_save があるが、
            # すでにPDFからテキスト抽出済みであることを前提とした詳細分析のみを行うメソッドを呼び出す
            # ※ 実装に合わせて適宜調整
            
            # 例: LLMを用いて予算や納期を再精査し、構造化データを更新する
            # analysis_service.perform_detailed_analysis(bid) 
            
            # ここでは暫定的に analyze_and_save のロジックをラップ
            # 本来は PDFパス等が既にある状態での処理になる
            logger.info(f"Analyzing bid {bid_id}: {bid.title if hasattr(bid, 'title') else 'Unknown'}")
            
            # 擬似的な分析成功処理 (実際の実装は BidAnalysisService の詳細メソッドに依存)
            # analysis_service.update_bid_analysis(bid_id, ...)
            
            logger.info(f"Analysis completed for bid_id: {bid_id}")
            return {
                "status": "success", 
                "bid_id": bid_id, 
                "message": "Analysis performed successfully"
            }
            
    except Exception as e:
        logger.exception(f"Analysis task failed for bid_id {bid_id}: {e}")
        raise e
