import logging
from typing import Dict, Any
from database.session import SessionLocal
from services.pdf_pipeline import PDFPipeline
from services.bid_analysis_service import BidAnalysisService
from services.llm_service import LLMService
from config_dir import AppConfig

logger = logging.getLogger(__name__)

def download_and_extract_task(bid_url: str, agency_id: int):
    """
    RQワーカーによって実行されるPDFダウンロードおよびテキスト抽出タスク。
    
    Args:
        bid_url (str): ダウンロード対象のPDF URL
        agency_id (int): 機関ID
    """
    logger.info(f"Starting PDF process task: {bid_url} for agency {agency_id}")
    
    try:
        # 1. サービスの初期化
        pdf_pipeline = PDFPipeline()
        config = AppConfig()
        
        # 2. テキスト抽出の実行
        # pdf_pipeline.extract_text_from_pdf は async メソッドのため、
        # RQワーカー（同期）で動かす場合は asyncio.run() 等でラップするか、
        # 同期版のメソッドを呼び出す必要がある
        import asyncio
        text = asyncio.run(pdf_pipeline.extract_text_from_pdf(bid_url))
        
        if not text:
            logger.warning(f"No text extracted from PDF: {bid_url}")
            return {"status": "failed", "reason": "empty_text", "url": bid_url}

        # 3. 抽出したテキストの保存または次の分析タスクへ
        # ここでは現状の設計に基づき、後続の分析タスクを呼び出すための準備として
        # テキストを一時的に保存するか、直接分析サービスを呼ぶ
        with SessionLocal() as db:
            analysis_service = BidAnalysisService(session=db)
            # PDFパスが必要なため、一時ファイルとして保存して渡す
            import tempfile
            import requests
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                response = requests.get(bid_url, timeout=60)
                tmp.write(response.content)
                tmp_path = tmp.name
            
            try:
                analysis_service.analyze_and_save(
                    pdf_path=tmp_path,
                    source_url=bid_url,
                    agency_id=agency_id
                )
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        logger.info(f"Successfully processed PDF: {bid_url}")
        return {"status": "success", "url": bid_url}

    except Exception as e:
        logger.exception(f"PDF process task failed for {bid_url}: {e}")
        raise e
