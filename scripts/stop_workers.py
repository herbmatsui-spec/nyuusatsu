"""
RQワーカー停止スクリプト（グレースフル）

Usage:
    py -3 scripts/stop_workers.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rq import Worker
from database.redis_conn import redis_conn

def main():
    workers = Worker.all(connection=redis_conn)
    if not workers:
        print("稼働中のWorkerはありません")
        return

    for w in workers:
        print(f"Sending shutdown request to {w.name}...")
        # RQのWorkerにシャットダウン要求を送信します（処理中のジョブ完了後に終了）
        w.request_stop(signum=None, frame=None)
        print(f"  -> {w.name} にシャットダウン要求送信完了")

    print(f"\n{len(workers)}件のWorkerにシャットダウン要求を送信しました")

if __name__ == "__main__":
    main()
