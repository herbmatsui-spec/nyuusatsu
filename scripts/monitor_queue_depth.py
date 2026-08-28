"""
キュー深度監視スクリプト。Waiting > 100 で警告を表示する。

Usage:
    py -3 scripts/monitor_queue_depth.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.health_checker import HealthChecker, HealthStatus

def main():
    checker = HealthChecker(queue_alert_threshold=100)
    result = checker.check_queue_depth()
    
    print("=" * 60)
    print("Queue Depth Status Check")
    print("=" * 60)
    
    for q_name, q_info in result.details.items():
        depth = q_info["waiting"]
        status = "⚠️ ALERT" if depth > 100 else "✅ OK"
        print(f"[{q_name}] Waiting: {depth} {status}")

    if result.status != HealthStatus.HEALTHY:
        print(f"\n🚨 {result.message}")
        sys.exit(1)
    else:
        print("\n全キュー正常")
        sys.exit(0)

if __name__ == "__main__":
    main()
