"""
APScheduler 起動スクリプト

Usage:
    py -3 run_scheduler.py
"""
import signal
import sys
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("RunScheduler")

from scheduler import scheduler_manager


def graceful_shutdown(signum, frame):
    logger.info("Received shutdown signal. Stopping scheduler...")
    scheduler_manager.stop()
    sys.exit(0)


def main():
    # SIGTERMとSIGINTでグレースフルシャットダウン
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)

    logger.info("Starting scheduler...")
    scheduler_manager.start()

    # スケジュール中のジョブ一覧を表示
    jobs = scheduler_manager.list_jobs()
    logger.info(f"Scheduled jobs: {len(jobs)}")
    for job in jobs:
        logger.info(f"  - {job.id}: next_run={job.next_run_time}")

    # 永続実行
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        graceful_shutdown(None, None)


if __name__ == "__main__":
    main()
