import pytest
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from crawler.models.crawl_result import CrawlResult
from services.pipeline_service import PipelineService
from services.bid_analysis_service import BidAnalysisService

class MockCrawlResult(CrawlResult):
    def __init__(self, url, title="Test PDF"):
        self.url = url
        self.title = title

@pytest.fixture
def mock_analysis_service():
    # BidAnalysisService requires a session
    session = MagicMock()
    service = BidAnalysisService(session=session)
    service.analyze_and_save = MagicMock(return_value=MagicMock())
    return service

@pytest.fixture
def pipeline_service(mock_analysis_service):
    return PipelineService(analysis_service=mock_analysis_service)

def test_pipeline_process_crawl_results_success(pipeline_service, mock_analysis_service):
    # Mock downloader to avoid real network requests
    with patch('crawler.downloader.Downloader.download_pdf', return_value=True):
        # Mock PDF file existence for the analysis service
        with patch('os.path.exists', return_value=True):
            # Mock text extraction to avoid needing a real PDF
            with patch('services.bid_analysis_service.BidAnalysisService.extract_text_from_pdf', return_value="Sample PDF Content"):
                # Mock LLM service
                with patch('services.llm_service.LLMService.analyze_with_fallback', return_value={"budget": "100万円"}):
                    
                    results = [
                        MockCrawlResult("https://example.com/bid1.pdf"),
                        MockCrawlResult("https://example.com/bid2.pdf")
                    ]
                    
                    res = pipeline_service.process_crawl_results(results, "Test Agency")
                    
                    assert res["processed"] == 2
                    assert res["failed"] == 0
                    assert mock_analysis_service.analyze_and_save.call_count == 2

def test_pipeline_process_crawl_results_non_pdf(pipeline_service, mock_analysis_service):
    results = [
        MockCrawlResult("https://example.com/page.html"), # Should be skipped
        MockCrawlResult("https://example.com/bid1.pdf")
    ]
    
    with patch('crawler.downloader.Downloader.download_pdf', return_value=True):
        with patch('os.path.exists', return_value=True):
            with patch('services.bid_analysis_service.BidAnalysisService.extract_text_from_pdf', return_value="Content"):
                with patch('services.llm_service.LLMService.analyze_with_fallback', return_value={}):
                    res = pipeline_service.process_crawl_results(results, "Test Agency")
                    assert res["processed"] == 1
                    assert res["failed"] == 0

def test_pipeline_process_crawl_results_download_fail(pipeline_service, mock_analysis_service):
    with patch('crawler.downloader.Downloader.download_pdf', return_value=False):
        results = [MockCrawlResult("https://example.com/fail.pdf")]
        res = pipeline_service.process_crawl_results(results, "Test Agency")
        assert res["processed"] == 0
        assert res["failed"] == 1
