import os
import sys
from redis import Redis

# プロジェクトルートをインポートパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.pipeline import trigger_agency_crawl, redis_conn, crawl_queue, download_queue

def verify_redis_connection():
    print("Checking Redis connection...")
    try:
        # pingを送信して疎通確認
        pong = redis_conn.ping()
        if pong:
            print("Successfully connected to Redis!")
            print(f"Redis Info: {redis_conn.info('server')['redis_version']}")
            return True
    except Exception as e:
        print("Error: Could not connect to Redis server.")
        print(f"Details: {e}")
        print("\nTo start a local Redis server, you can run:")
        print("docker run -d -p 6379:6379 redis")
        print("Or start the native Redis service if installed.")
        return False

def verify_pipeline_queues():
    print("\nChecking RQ Queues...")
    try:
        print(f"Queue 'crawl_tasks' length: {len(crawl_queue)}")
        print(f"Queue 'download_tasks' length: {len(download_queue)}")
        
        # テストタスクをエンキューしてみる
        print("\nEnqueuing a test crawl task for config ID 999...")
        job = crawl_queue.enqueue("crawler.pipeline.crawl_agency_task", 999)
        print(f"Job enqueued. Job ID: {job.id}, Status: {job.get_status()}")
        
        # キャンセル（テスト用なので実行させずに消す）
        job.cancel()
        print("Test job cancelled successfully.")
        return True
    except Exception as e:
        print(f"Error during queue verification: {e}")
        return False

if __name__ == "__main__":
    if verify_redis_connection():
        verify_pipeline_queues()
    else:
        sys.exit(1)
