"""
失敗ジョブ再試行スクリプト

Usage:
    py -3 scripts/retry_failed_jobs.py
    py -3 scripts/retry_failed_jobs.py --queue crawl_tasks
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from rq import Queue
from database.redis_conn import redis_conn

QUEUE_NAMES = ["crawl_tasks", "download_tasks", "analysis_tasks", "notification_tasks"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=str, default=None, help="対象キュー名（未指定で全キュー）")
    parser.add_argument("--max", type=int, default=10, help="最大再試行数")
    args = parser.parse_args()

    queues = [args.queue] if args.queue else QUEUE_NAMES
    total_retried = 0

    for name in queues:
        q = Queue(name, connection=redis_conn)
        failed_count = q.failed_job_registry.count
        if failed_count == 0:
            print(f"[{name}] 失敗ジョブなし")
            continue

        print(f"[{name}] 失敗ジョブ: {failed_count}件")
        retried = 0
        for job_id in q.failed_job_registry.get_job_ids():
            if retried >= args.max:
                break
            try:
                q.failed_job_registry.requeue(job_id)
                retried += 1
                total_retried += 1
                print(f"  再キュー: {job_id}")
            except Exception as e:
                print(f"  失敗: {job_id} - {e}")

    print(f"\n合計 {total_retried} 件を再キューしました")

if __name__ == "__main__":
    main()
