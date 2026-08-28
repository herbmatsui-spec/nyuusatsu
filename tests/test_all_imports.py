"""全モジュールのimportテスト"""
import pytest

def test_database_models():
    from database.models import (
        Bid, BidStatus, Customer, Partner, Agency,
        CrawlConfig, CrawlLog, CrawlHistory, CrawledUrl,
        PDFDocument, Prefecture, BidSource, CrawlJob,
    )

def test_repositories():
    from database.repositories.bid_repository import BidRepository
    from database.repositories.agency_repository import AgencyRepository
    from database.repositories.pdf_repository import PDFRepository

def test_services():
    from services.bid_service import BidService
    from services.bid_analysis_service import BidAnalysisService

def test_crawler():
    from crawler.generic_crawler import GenericCrawler
    from crawler.downloader import PDFDownloader, Downloader
    from crawler.base_crawler import BaseCrawler
    from crawler.parsers.heuristic_parser import HeuristicParser

def test_pipeline():
    from crawler.pipeline import (
        trigger_agency_crawl, crawl_agency_task,
        download_pdf_task, analyze_pdf_task,
    )

def test_scheduler():
    from scheduler import scheduler_manager

def test_redis_conn():
    from database.redis_conn import redis_conn
