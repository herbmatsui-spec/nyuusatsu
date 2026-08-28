import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime
from config import AppConfig
from services.crawl_service import CrawlService

config = AppConfig()

def collect_bid_urls(url: str) -> list:
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        bids = []
        for a in soup.find_all('a', href=True):
            if 'bid' in a['href'] or 'detail' in a['href']:
                full_url = a['href'] if a['href'].startswith('http') else requests.compat.urljoin(url, a['href'])
                bids.append({'title': a.text.strip() or "名称不明", 'url': full_url})
        return bids
    except Exception as e:
        logging.error(f"URL収集エラー: {e}")
        return []

def execute_crawl():
    logging.info("巡回タスクを開始します...")
    from database.engine import SessionLocal
    session = SessionLocal()
    try:
        all_bids = collect_bid_urls(config.crawler.target_url)
        url_count = len(all_bids)
        new_count = url_count
        
        crawl_service = CrawlService(session)
        crawl_service.record_crawl_history(url_count=url_count, new_count=new_count, status="SUCCESS")
        
        return {"success": True, "url_count": url_count, "new_count": new_count}
    except Exception as e:
        logging.error(f"巡回タスクエラー: {e}")
        try:
            crawl_service = CrawlService(session)
            crawl_service.record_crawl_history(url_count=0, new_count=0, status="FAILED", error_message=str(e))
        except:
            pass
        return {"success": False, "error": str(e)}
    finally:
        session.close()
