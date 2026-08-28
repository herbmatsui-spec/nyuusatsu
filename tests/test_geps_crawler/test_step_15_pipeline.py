from crawler.pipeline import download_pdf_task, analyze_pdf_task
from crawler.pipeline import crawl_agency_task, trigger_agency_crawl
from crawler.pipeline import send_new_bid_notification_task

def test_download_pdf_task_exists():
    """download_pdf_task関数が存在し呼び出し可能か"""
    assert callable(download_pdf_task)

def test_analyze_pdf_task_exists():
    """analyze_pdf_task関数が存在し呼び出し可能か"""
    assert callable(analyze_pdf_task)

def test_crawl_agency_task_exists():
    """crawl_agency_task関数が存在し呼び出し可能か"""
    assert callable(crawl_agency_task)

def test_trigger_agency_crawl_exists():
    """trigger_agency_crawl関数が存在し呼び出し可能か"""
    assert callable(trigger_agency_crawl)

def test_notification_task_exists():
    """send_new_bid_notification_task関数が存在し呼び出し可能か"""
    assert callable(send_new_bid_notification_task)

def test_pipeline_queues_importable():
    """パイプラインの各キューがインポート可能か"""
    try:
        from crawler.pipeline import crawl_queue, download_queue, analysis_queue, notification_queue
        imported = True
    except ImportError:
        imported = False
    assert imported == True

def test_pipeline_redis_connection_importable():
    """Redis接続がインポート可能か"""
    try:
        from database.redis_conn import redis_conn
        imported = True
    except ImportError:
        imported = False
    assert imported == True
