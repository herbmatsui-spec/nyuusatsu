from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime
import uuid

class BaseEvent(BaseModel):
    """すべてのイベントの基底クラス"""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trace_id: str = Field(..., description="リクエストを追跡するための共通ID")
    payload: Dict[str, Any] = Field(default_factory=dict)

class CrawlRequested(BaseEvent):
    """クロールリクエストイベント"""
    # payload: {"agency_id": int, "prefecture_id": int}
    pass

class PDFDownloaded(BaseEvent):
    """PDFダウンロード完了イベント"""
    # payload: {"bid_id": int, "pdf_path": str, "url": str}
    pass

class TextExtracted(BaseEvent):
    """テキスト抽出完了イベント"""
    # payload: {"bid_id": int, "text": str, "method": "pdfplumber" | "ocr"}
    pass

class AnalysisCompleted(BaseEvent):
    """LLM分析完了イベント"""
    # payload: {"bid_id": int, "analysis_result": dict}
    pass

class AnalysisFailed(BaseEvent):
    """分析失敗イベント"""
    # payload: {"bid_id": int, "error": str, "stage": "extraction" | "analysis"}
    pass
