"""
SQLiteベースの軽量タスクキュー（Redis/RQ不要）。
Redis 6+ が利用可能な環境では RQ に置き換え可能。

タスク投入:
    from services.sqlite_task_queue import task_queue
    task_queue.enqueue(crawl_agency_task, config_id)

ワーカー起動:
    python -m services.sqlite_task_queue
"""
import sys
import os
import threading
import time
import logging
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
import pickle

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from database.engine import engine, SessionLocal
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, func
from sqlalchemy.orm import Session

logger = logging.getLogger("TaskQueue")


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(Base):
    __tablename__ = "async_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(255), nullable=False, index=True)
    task_func = Column(String(512), nullable=False)
    args = Column(Text, nullable=True)
    kwargs = Column(Text, nullable=True)
    status = Column(String(20), default=TaskStatus.PENDING, nullable=False, index=True)
    enqueued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime, nullable=True)
    priority = Column(Integer, default=0)


class SQLiteTaskQueue:
    """
    SQLiteベースのFIFOタスクキュー。
    RQの代わりに使用可能。ワーカーがポーリングでタスクを取得・実行する。
    """

    def __init__(self, poll_interval: float = 5.0, max_concurrent: int = 4):
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
        self._running = False
        self._lock = threading.Lock()
        Base.metadata.create_all(bind=engine)

    def enqueue(self, func: Callable, *args, **kwargs) -> int:
        """タスクをキューに追加。func は module.func_name 形式の文字列で保存"""
        if callable(func):
            func_ref = f"{func.__module__}.{func.__qualname__}"
        else:
            func_ref = str(func)

        task = Task(
            task_func=func_ref,
            args=pickle.dumps(args).hex(),
            kwargs=pickle.dumps(kwargs).hex(),
            status=TaskStatus.PENDING,
            priority=kwargs.pop("_priority", 0),
        )

        with Session(bind=engine) as session:
            session.add(task)
            session.commit()
            task_id = task.id

        logger.info(f"Enqueued task {task_id}: {func_ref}")
        return task_id

    def enqueue_crawl(self, crawl_config_id: int) -> int:
        """クロールタスクを投入する便捷メソッド"""
        return self.enqueue("crawler.pipeline.crawl_agency_task", crawl_config_id)

    def get_pending_tasks(self, limit: int = 10) -> List[Task]:
        now = datetime.utcnow()
        with Session(bind=engine) as session:
            tasks = (
                session.query(Task)
                .filter(
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.FAILED]),
                    (Task.next_retry_at.is_(None) | (Task.next_retry_at <= now)),
                )
                .order_by(Task.priority.desc(), Task.enqueued_at.asc())
                .limit(limit)
                .all()
            )
            return list(tasks)

    def mark_running(self, task: Task) -> None:
        with Session(bind=engine) as session:
            t = session.get(Task, task.id)
            if t:
                t.status = TaskStatus.RUNNING
                t.started_at = datetime.utcnow()
                session.commit()

    def mark_completed(self, task: Task, result: Any = None) -> None:
        with Session(bind=engine) as session:
            t = session.get(Task, task.id)
            if t:
                t.status = TaskStatus.COMPLETED
                t.completed_at = datetime.utcnow()
                t.result = pickle.dumps(result).hex() if result else None
                session.commit()

    def mark_failed(self, task: Task, error: str) -> None:
        with Session(bind=engine) as session:
            t = session.get(Task, task.id)
            if t:
                t.retry_count = (t.retry_count or 0) + 1
                if t.retry_count < t.max_retries:
                    t.status = TaskStatus.PENDING
                    t.next_retry_at = datetime.utcnow() + timedelta(
                        seconds=2 ** t.retry_count * 10
                    )
                    t.error = error
                    logger.info(f"Task {t.id} scheduled for retry #{t.retry_count}")
                else:
                    t.status = TaskStatus.FAILED
                    t.completed_at = datetime.utcnow()
                    t.error = error
                    logger.warning(f"Task {t.id} failed permanently after {t.retry_count} retries")
                session.commit()

    def execute_task(self, task: Task) -> Any:
        module_name, func_name = task.task_func.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name)

        args = pickle.loads(bytes.fromhex(task.args)) if task.args else ()
        kwargs = pickle.loads(bytes.fromhex(task.kwargs)) if task.kwargs else {}

        return func(*args, **kwargs)

    def run_once(self, limit: int = 10) -> int:
        tasks = self.get_pending_tasks(limit)
        if not tasks:
            return 0

        for task in tasks:
            self.mark_running(task)
            try:
                result = self.execute_task(task)
                self.mark_completed(task, result)
            except Exception as e:
                self.mark_failed(task, traceback.format_exc())

        return len(tasks)

    def run(self) -> None:
        logger.info(f"SQLiteTaskQueue worker started. Poll interval: {self.poll_interval}s, max_concurrent: {self.max_concurrent}")
        self._running = True

        import concurrent.futures
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent)

        while self._running:
            try:
                tasks = self.get_pending_tasks(limit=self.max_concurrent * 2)
                if tasks:
                    for task in tasks:
                        if not self._running:
                            break
                        pool.submit(self._process_task, task)
            except Exception as e:
                logger.error(f"Queue poll error: {e}")

            time.sleep(self.poll_interval)

        pool.shutdown(wait=True)
        logger.info("SQLiteTaskQueue worker stopped.")

    def _process_task(self, task: Task) -> None:
        from services.metrics_collector import BufferedMetricsCollector
        stage = "task_queue"
        labels = {"task_id": task.id, "task_func": task.task_func}
        try:
            self.mark_running(task)
            
            # タスク実行時間を計測
            with BufferedMetricsCollector.measure(stage, "duration_ms", labels=labels):
                result = self.execute_task(task)
                
            self.mark_completed(task, result)
            BufferedMetricsCollector.record(stage, "success", 1.0, labels=labels)
        except Exception as e:
            self.mark_failed(task, traceback.format_exc())
            BufferedMetricsCollector.record(stage, "success", 0.0, labels={"task_id": task.id, "task_func": task.task_func, "error": str(type(e).__name__)})
        finally:
            BufferedMetricsCollector.flush()

    def stop(self) -> None:
        self._running = False

    def stats(self) -> Dict[str, int]:
        with Session(bind=engine) as session:
            pending = session.query(Task).filter_by(status=TaskStatus.PENDING).count()
            running = session.query(Task).filter_by(status=TaskStatus.RUNNING).count()
            completed = session.query(Task).filter_by(status=TaskStatus.COMPLETED).count()
            failed = session.query(Task).filter_by(status=TaskStatus.FAILED).count()
            return {
                "pending": pending,
                "running": running,
                "completed": completed,
                "failed": failed,
            }


task_queue = SQLiteTaskQueue(poll_interval=5.0, max_concurrent=4)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    print("Starting SQLite TaskQueue worker...")
    print("Press Ctrl+C to stop.")
    try:
        task_queue.run()
    except KeyboardInterrupt:
        print("\nStopping...")
        task_queue.stop()


if __name__ == "__main__":
    main()