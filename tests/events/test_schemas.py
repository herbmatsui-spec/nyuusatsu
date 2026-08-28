import pytest
from events.schemas import BaseEvent, CrawlRequested, PDFDownloaded, TextExtracted, AnalysisCompleted, AnalysisFailed
from datetime import datetime
import uuid

def test_base_event_defaults():
    """BaseEventのデフォルト値が正しく設定されるか検証"""
    event = BaseEvent(trace_id="test-trace-123", payload={"key": "value"})
    assert event.event_id is not None
    assert isinstance(event.timestamp, datetime)
    assert event.trace_id == "test-trace-123"
    assert event.payload == {"key": "value"}

def test_crawl_requested_schema():
    """CrawlRequestedイベントのバリデーション検証"""
    payload = {"agency_id": 1, "prefecture_id": 11}
    event = CrawlRequested(trace_id="trace-crawl", payload=payload)
    assert event.payload["agency_id"] == 1
    assert event.payload["prefecture_id"] == 11

def test_pdf_downloaded_schema():
    """PDFDownloadedイベントのバリデーション検証"""
    payload = {"bid_id": 100, "pdf_path": "/tmp/bid.pdf", "url": "http://example.com/bid.pdf"}
    event = PDFDownloaded(trace_id="trace-pdf", payload=payload)
    assert event.payload["bid_id"] == 100
    assert event.payload["pdf_path"] == "/tmp/bid.pdf"

def test_text_extracted_schema():
    """TextExtractedイベントのバリデーション検証"""
    payload = {"bid_id": 100, "text": "extracted text", "method": "ocr"}
    event = TextExtracted(trace_id="trace-text", payload=payload)
    assert event.payload["method"] == "ocr"

def test_analysis_completed_schema():
    """AnalysisCompletedイベントのバリデーション検証"""
    payload = {"bid_id": 100, "analysis_result": {"budget": "100万円"}}
    event = AnalysisCompleted(trace_id="trace-analysis", payload=payload)
    assert event.payload["analysis_result"]["budget"] == "100万円"

def test_analysis_failed_schema():
    """AnalysisFailedイベントのバリデーション検証"""
    payload = {"bid_id": 100, "error": "timeout", "stage": "analysis"}
    event = AnalysisFailed(trace_id="trace-fail", payload=payload)
    assert event.payload["stage"] == "analysis"
    assert event.payload["error"] == "timeout"
