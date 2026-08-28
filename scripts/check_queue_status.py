"""
RQキュー状況確認スクリプト

Usage:
    py -3 scripts/check_queue_status.py
"""
import sys
import os
import io

import sys
import os
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from services.health_checker import HealthChecker

def main():
    checker = HealthChecker()
    result = checker.check_queue_depth()
    
    print("=" * 60)
    print("RQ Queue Status (via HealthChecker)")
    print("=" * 60)

    for name, details in result.details.items():
        print(f"\n[{name}]")
        print(f"  Waiting:  {details['waiting']}")
        print(f"  Started:  {details['started']}")
        print(f"  Failed:   {details['failed']}")

    # Worker情報
    try:
        from rq import Worker
        from database.redis_conn import redis_conn
        workers = Worker.all(connection=redis_conn)
        print(f"\n{'=' * 60}")
        print(f"Active Workers: {len(workers)}")
        for w in workers:
            print(f"  - {w.name} (state={w.state}, queues={[q.name for q in w.queues]})")
    except Exception as e:
        print(f"\nCould not fetch active workers: {e}")

if __name__ == "__main__":
    main()
