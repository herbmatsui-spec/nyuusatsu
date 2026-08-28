import logging
import argparse
import sys
from rq import Worker, Connection
from queue.rq_config import rq_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("RQWorker")

def main():
    parser = argparse.ArgumentParser(description="Redis RQ Worker for Bid System")
    parser.add_argument(
        "--queue", 
        type=str, 
        required=True, 
        help="Queue name to listen to (crawl, pdf_process, analysis, notification)"
    )
    
    args = parser.parse_args()
    queue_name = args.queue

    logger.info(f"Starting RQ Worker for queue: {queue_name}")

    try:
        # Redis接続を使用してWorkerを起動
        with Connection(rq_config.redis_conn):
            worker = Worker([queue_name])
            worker.work()
    except Exception as e:
        logger.exception(f"Worker crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
