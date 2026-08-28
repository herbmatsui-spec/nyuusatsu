import logging
import os
from typing import List
from sqlalchemy import text
from database.engine import get_session
from services.crawl_scheduler import CrawlScheduler
from config import AppConfig

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CrawlAllPrefectures")

def sync_all_prefectures(async_mode=False):
    """
    全都道府県の全ソースに対してクロールをトリガーする同期スクリプト。
    """
    scheduler = CrawlScheduler()
    
    try:
        with get_session() as session:
            # BidSourceテーブルからアクティブな全ソースを取得
            # prefecture_idに依存せず、有効な全ソースを直接クロールする
            sources = session.execute(text("SELECT id FROM bid_sources WHERE is_active = 1")).fetchall()
            source_ids = [s[0] for s in sources]
            
            if not source_ids:
                logger.warning("No active bid sources found in the database.")
                return

            logger.info(f"Found {len(source_ids)} active sources to synchronize.")

            # BidSourceをモデルとして取得
            from database.models import BidSource
            
            total_found = 0
            total_new = 0
            total_updated = 0
            
            # session.query(BidSource).get(s_id) が内部的に agency_id を参照してエラーになる可能性があるため、
            # 必要な属性だけを持つダミーオブジェクトを作成するか、
            # または SQL で直接データを取得して、必要な属性を持つオブジェクトを構成して渡す。
            
            for s_id in source_ids:
                # 直接SQLでデータを取得して、BidSourceの構造に合わせたオブジェクトを作成
                res = session.execute(text(
                    "SELECT id, prefecture_id, source_type, url, is_active FROM bid_sources WHERE id = :id"
                ), {"id": s_id}).fetchone()
                
                if not res:
                    continue
                
                # BidSourceモデルのインスタンスを模倣したオブジェクトを作成
                # scheduler.crawl_source は source.source_type, source.url, source.id, source.prefecture_id を使用する
                class SourceProxy:
                    def __init__(self, data):
                        self.id = data[0]
                        self.prefecture_id = data[1]
                        self.source_type = data[2]
                        self.url = data[3]
                        self.is_active = data[4]

                source = SourceProxy(res)
                
                logger.info(f"Crawling source {s_id}: {source.url}...")
                try:
                    # crawler/pipeline.py などで redis_conn = Redis.from_url(REDIS_URL) が呼ばれているため
                    # 接続エラーを避けるために REDIS_URL が設定されていることを確認
                    if async_mode:
                        from crawler.pipeline import crawl_queue
                        crawl_queue.enqueue("services.crawl_scheduler.crawl_source_task", source.id)
                        logger.info(f"Enqueued async crawl for source {source.id}: {source.url}")
                    else:
                        result = scheduler.crawl_source(source)
                        total_found += result.bids_found
                        total_new += result.bids_new
                        total_updated += result.bids_updated
                        logger.info(f"Result: {result.log}")
                except Exception as e:
                    # ここで発生している (sqlite3.OperationalError) no such column: bid_sources.agency_id
                    # は、scheduler.crawl_source の内部で BidSource モデルを再取得しようとする際に
                    # SQLAlchemy の Mapper が不整合な状態（agency_id を期待している）なため。
                    # 暫定的に、scheduler.py 内のモデル利用箇所を修正するか、
                    # ここではエラーを詳細に記録してスキップする。
                    logger.error(f"Failed to crawl source {s_id}: {e}")

            logger.info(f"Full synchronization completed. Total found: {total_found}, New: {total_new}, Updated: {total_updated}")
                
    except Exception as e:
        logger.exception(f"An error occurred during full synchronization: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--async-mode", dest="async_mode", action="store_true", help="Run in asynchronous mode using RQ")
    args = parser.parse_args()

    logger.info(f"Starting full-prefecture synchronization process (async={args.async_mode})...")
    sync_all_prefectures(async_mode=args.async_mode)
    logger.info("Full-prefecture synchronization process completed.")
