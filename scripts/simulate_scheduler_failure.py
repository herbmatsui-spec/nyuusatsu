#!/usr/bin/env python3
"""
スケジューラ障害シミュレーション - 混沌工学的アプローチでレジリエンスを検証 (Step 47)。

使用例:
    python scripts/simulate_scheduler_failure.py --scenario transient --job daily_crawl
    python scripts/simulate_scheduler_failure.py --scenario fatal --job forecast_crawl_job
    python scripts/simulate_scheduler_failure.py --scenario config --job url_monitor_job
    python scripts/simulate_scheduler_failure.py --scenario dlq_overflow --count 10
    python scripts/simulate_scheduler_failure.py --scenario worker_crash
"""

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler import (
    SchedulerManager,
    TransientError,
    FatalError,
    ConfigurationError,
    _enqueue_dlq,
    retry_dlq_jobs,
    _DEAD_LETTER_QUEUE_PATH,
    _SCHEDULER_MAX_RETRIES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FailureSimulator:
    """スケジューラ障害シミュレータ。"""
    
    def __init__(self):
        self.manager = SchedulerManager()
        self.manager.scheduler = None  # 実際のスケジューラは使わない
        self.results = []
    
    def simulate_transient_error(self, job_id: str, fail_count: int = 3) -> dict:
        """一時的エラーをシミュレート（リトライで復旧）。"""
        logger.info(f"=== Simulating TransientError for {job_id} (fail {fail_count} times) ===")
        
        call_count = [0]
        
        def flaky_func():
            call_count[0] += 1
            if call_count[0] <= fail_count:
                raise TransientError(f"Simulated transient failure #{call_count[0]}")
            return f"Recovered after {call_count[0]} attempts"
        
        start = time.time()
        try:
            result = self.manager._safe_run_job(job_id, flaky_func)
            duration = time.time() - start
            logger.info(f"SUCCESS: {result} (duration: {duration:.2f}s)")
            return {"job_id": job_id, "scenario": "transient", "success": True, "attempts": call_count[0], "duration": duration}
        except Exception as e:
            duration = time.time() - start
            logger.error(f"FAILED: {e} (duration: {duration:.2f}s)")
            return {"job_id": job_id, "scenario": "transient", "success": False, "error": str(e), "duration": duration}
    
    def simulate_fatal_error(self, job_id: str) -> dict:
        """致命的エラーをシミュレート（即DLQ行き）。"""
        logger.info(f"=== Simulating FatalError for {job_id} ===")
        
        def fatal_func():
            raise FatalError("Simulated fatal error: data corruption detected")
        
        start = time.time()
        try:
            result = self.manager._safe_run_job(job_id, fatal_func)
            duration = time.time() - start
            return {"job_id": job_id, "scenario": "fatal", "success": True, "duration": duration}
        except Exception as e:
            duration = time.time() - start
            logger.error(f"EXPECTED DLQ: {e} (duration: {duration:.2f}s)")
            return {"job_id": job_id, "scenario": "fatal", "success": False, "dlq": True, "error": str(e), "duration": duration}
    
    def simulate_config_error(self, job_id: str) -> dict:
        """設定エラーをシミュレート（即DLQ行き + 通知）。"""
        logger.info(f"=== Simulating ConfigurationError for {job_id} ===")
        
        def config_func():
            raise ConfigurationError("Simulated config error: missing required environment variable")
        
        start = time.time()
        try:
            result = self.manager._safe_run_job(job_id, config_func)
            duration = time.time() - start
            return {"job_id": job_id, "scenario": "config", "success": True, "duration": duration}
        except Exception as e:
            duration = time.time() - start
            logger.error(f"EXPECTED DLQ+NOTIFY: {e} (duration: {duration:.2f}s)")
            return {"job_id": job_id, "scenario": "config", "success": False, "dlq": True, "notify": True, "error": str(e), "duration": duration}
    
    def simulate_dlq_overflow(self, count: int = 10) -> dict:
        """DLQ溢れをシミュレート（大量の失敗ジョブ投入）。"""
        logger.info(f"=== Simulating DLQ Overflow ({count} jobs) ===")
        
        for i in range(count):
            job_id = f"overflow_job_{i}"
            _enqueue_dlq(job_id, f"Simulated error #{i}", {"iteration": i})
        
        # DLQファイルサイズ確認
        if _DEAD_LETTER_QUEUE_PATH.exists():
            size = _DEAD_LETTER_QUEUE_PATH.stat().st_size
            with open(_DEAD_LETTER_QUEUE_PATH) as f:
                entries = json.load(f)
            logger.info(f"DLQ entries: {len(entries)}, file size: {size} bytes")
            return {"scenario": "dlq_overflow", "entries": len(entries), "file_size": size}
        return {"scenario": "dlq_overflow", "entries": 0}
    
    def simulate_worker_crash(self) -> dict:
        """ワーカークラッシュをシミュレート（プロセス強制終了）。"""
        logger.info("=== Simulating Worker Crash ===")
        logger.warning("This will terminate the current process! Use with caution.")
        
        # 実際のクラッシュは危険なので、エラーログのみ出力
        logger.critical("SIMULATED WORKER CRASH - Process would exit here")
        logger.critical("In real scenario: os._exit(1) or signal.SIGKILL")
        
        return {"scenario": "worker_crash", "simulated": True}
    
    def simulate_retry_exhaustion(self, job_id: str) -> dict:
        """最大リトライ超過をシミュレート。"""
        logger.info(f"=== Simulating Retry Exhaustion for {job_id} (max_retries={_SCHEDULER_MAX_RETRIES}) ===")
        
        def always_fail():
            raise TransientError("Persistent simulated failure")
        
        start = time.time()
        try:
            result = self.manager._safe_run_job(job_id, always_fail)
            duration = time.time() - start
            return {"job_id": job_id, "scenario": "retry_exhaustion", "success": True, "duration": duration}
        except Exception as e:
            duration = time.time() - start
            logger.error(f"EXPECTED DLQ after {_SCHEDULER_MAX_RETRIES} retries: {e}")
            return {"job_id": job_id, "scenario": "retry_exhaustion", "success": False, "dlq": True, "max_retries": _SCHEDULER_MAX_RETRIES, "duration": duration}
    
    def simulate_concurrent_failures(self, job_ids: List[str]) -> dict:
        """複数ジョブの同時失敗をシミュレート。"""
        logger.info(f"=== Simulating Concurrent Failures for {len(job_ids)} jobs ===")
        
        results = []
        for job_id in job_ids:
            # ランダムにエラータイプ選択
            error_type = random.choice(["transient", "fatal", "config"])
            
            if error_type == "transient":
                r = self.simulate_transient_error(job_id, fail_count=2)
            elif error_type == "fatal":
                r = self.simulate_fatal_error(job_id)
            else:
                r = self.simulate_config_error(job_id)
            results.append(r)
        
        return {"scenario": "concurrent_failures", "results": results}
    
    def run_all_scenarios(self) -> List[dict]:
        """全シナリオを実行。"""
        logger.info("=== Running All Failure Scenarios ===")
        
        all_results = []
        
        # 1. Transient error with recovery
        all_results.append(self.simulate_transient_error("daily_crawl", fail_count=2))
        
        # 2. Transient error exceeding max retries
        all_results.append(self.simulate_retry_exhaustion("persistent_job"))
        
        # 3. Fatal error
        all_results.append(self.simulate_fatal_error("critical_job"))
        
        # 4. Config error
        all_results.append(self.simulate_config_error("misconfigured_job"))
        
        # 5. DLQ overflow
        all_results.append(self.simulate_dlq_overflow(5))
        
        # 6. Concurrent failures
        all_results.append(self.simulate_concurrent_failures([
            "job_a", "job_b", "job_c"
        ]))
        
        # 7. Worker crash (simulated)
        all_results.append(self.simulate_worker_crash())
        
        return all_results


def verify_dlq_contents():
    """DLQ内容を検証。"""
    if not _DEAD_LETTER_QUEUE_PATH.exists():
        logger.info("DLQ file not found")
        return []
    
    with open(_DEAD_LETTER_QUEUE_PATH) as f:
        entries = json.load(f)
    
    logger.info(f"DLQ contains {len(entries)} entries:")
    for entry in entries:
        logger.info(f"  - {entry['job_id']}: {entry['error']} (at {entry['failed_at']})")
    
    return entries


def cleanup_dlq():
    """DLQをクリーンアップ。"""
    if _DEAD_LETTER_QUEUE_PATH.exists():
        _DEAD_LETTER_QUEUE_PATH.unlink()
        logger.info("DLQ cleaned up")
    else:
        logger.info("DLQ already empty")


def test_dlq_retry():
    """DLQ再実行をテスト。"""
    logger.info("=== Testing DLQ Retry ===")
    
    # 失敗ジョブをDLQに追加
    _enqueue_dlq("test_retry_job", "Original error", {})
    
    # 再実行（モック）
    from unittest.mock import patch
    with patch("scheduler.execute_crawl", return_value={"new_count": 5}):
        result = retry_dlq_jobs(["test_retry_job"])
    
    logger.info(f"Retry result: {result}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Scheduler Failure Simulator")
    parser.add_argument(
        "--scenario",
        choices=["transient", "fatal", "config", "dlq_overflow", "worker_crash", 
                 "retry_exhaustion", "concurrent", "all"],
        default="all",
        help="Failure scenario to simulate"
    )
    parser.add_argument("--job", default="test_job", help="Job ID to target")
    parser.add_argument("--count", type=int, default=5, help="Count for overflow scenario")
    parser.add_argument("--fail-count", type=int, default=3, help="Fail count for transient")
    parser.add_argument("--verify-dlq", action="store_true", help="Verify DLQ after simulation")
    parser.add_argument("--cleanup-dlq", action="store_true", help="Cleanup DLQ before/after")
    parser.add_argument("--test-retry", action="store_true", help="Test DLQ retry")
    parser.add_argument("--output", type=Path, help="Output results to JSON file")
    
    args = parser.parse_args()
    
    if args.cleanup_dlq:
        cleanup_dlq()
    
    simulator = FailureSimulator()
    results = []
    
    if args.scenario == "transient":
        results.append(simulator.simulate_transient_error(args.job, args.fail_count))
    elif args.scenario == "fatal":
        results.append(simulator.simulate_fatal_error(args.job))
    elif args.scenario == "config":
        results.append(simulator.simulate_config_error(args.job))
    elif args.scenario == "dlq_overflow":
        results.append(simulator.simulate_dlq_overflow(args.count))
    elif args.scenario == "worker_crash":
        results.append(simulator.simulate_worker_crash())
    elif args.scenario == "retry_exhaustion":
        results.append(simulator.simulate_retry_exhaustion(args.job))
    elif args.scenario == "concurrent":
        results.append(simulator.simulate_concurrent_failures([
            f"{args.job}_1", f"{args.job}_2", f"{args.job}_3"
        ]))
    elif args.scenario == "all":
        results = simulator.run_all_scenarios()
    
    if args.test_retry:
        results.append(test_dlq_retry())
    
    if args.verify_dlq:
        verify_dlq_contents()
    
    if args.cleanup_dlq:
        cleanup_dlq()
    
    # 結果出力
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "scenario": args.scenario,
        "results": results,
    }
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Results written to {args.output}")
    else:
        print(json.dumps(output_data, indent=2, ensure_ascii=False))
    
    # 成功判定
    failed = [r for r in results if isinstance(r, dict) and r.get("success") is False and r.get("dlq") is not True]
    if failed:
        logger.warning(f"{len(failed)} unexpected failures")
        sys.exit(1)
    else:
        logger.info("All scenarios completed as expected")
        sys.exit(0)


if __name__ == "__main__":
    main()