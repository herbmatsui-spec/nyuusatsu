import pytest
from unittest.mock import MagicMock
from datetime import datetime
import json

from scheduler import SchedulerManager
from database.models.agency import Agency
from database.models.crawl_config import CrawlConfig


def test_sync_crawl_jobs(db_session, mocker):
    """Original sync_crawl_jobs test - patched at module level."""
    now = datetime.utcnow()
    agency1 = Agency(name="自治体A", type="municipality", region="東京都", created_at=now, updated_at=now)
    agency2 = Agency(name="自治体B", type="municipality", region="神奔川県", created_at=now, updated_at=now)
    db_session.add_all([agency1, agency2])
    db_session.commit()

    config1 = CrawlConfig(agency_id=agency1.id, target_url="https://example.com/a.html", parser_type="heuristic", frequency="hourly", is_active=True, created_at=now, updated_at=now)
    config2 = CrawlConfig(agency_id=agency2.id, target_url="https://example.com/b.html", parser_type="rss", frequency="daily", is_active=False, created_at=now, updated_at=now)
    db_session.add_all([config1, config2])
    db_session.commit()

    mock_get_db = mocker.patch("scheduler.scheduler.get_db")
    mock_get_db.return_value.__enter__.return_value = db_session

    mock_trigger = mocker.patch("scheduler.scheduler.trigger_agency_crawl")

    mgr = SchedulerManager()
    mgr.scheduler = MagicMock()
    mgr.scheduler.get_jobs.return_value = []

    mgr.sync_crawl_jobs()

    job_id = f"agency_crawl_{config1.id}"
    called_jobs = [call.kwargs.get('id') for call in mgr.scheduler.add_job.call_args_list]
    assert job_id in called_jobs


def test_safe_run_job_success(mocker):
    """Step 33-35: _safe_run_job should execute successfully without retry."""
    from scheduler import SchedulerManager, _reset_retry
    
    mgr = SchedulerManager()
    mgr.scheduler = MagicMock()
    mgr._max_retries = 3
    _reset_retry("test_job")
    
    mock_func = mocker.MagicMock(return_value="success_result")
    result = mgr._safe_run_job("test_job", mock_func, "arg1", kwarg1="val1")
    
    assert result == "success_result"
    mock_func.assert_called_once_with("arg1", kwarg1="val1")
    _reset_retry("test_job")


def test_safe_run_job_transient_error_retry(mocker):
    """Step 33-35: TransientError should trigger retry with backoff."""
    from scheduler import SchedulerManager, TransientError, _reset_retry, _compute_backoff
    
    mgr = SchedulerManager()
    mgr.scheduler = MagicMock()
    mgr._max_retries = 3
    _reset_retry("test_retry_job")
    
    call_count = [0]
    def flaky_func():
        call_count[0] += 1
        if call_count[0] < 3:
            raise TransientError("Temporary failure")
        return "recovered"
    
    mock_sleep = mocker.patch("scheduler.scheduler.time.sleep")
    result = mgr._safe_run_job("test_retry_job", flaky_func)
    
    assert result == "recovered"
    assert call_count[0] == 3
    assert mock_sleep.call_count == 2
    _reset_retry("test_retry_job")


def test_safe_run_job_transient_error_dlq(mocker):
    """Step 33-36: TransientError exceeding max retries goes to DLQ."""
    from scheduler import SchedulerManager, SchedulerManager as SM, TransientError, _reset_retry
    
    mgr = SchedulerManager()
    mgr.scheduler = MagicMock()
    mgr._max_retries = 2
    _reset_retry("test_dlq_job")
    
    mock_enqueue = mocker.patch("scheduler.scheduler._enqueue_dlq")
    mock_sleep = mocker.patch("scheduler.scheduler.time.sleep")
    
    def always_fail():
        raise TransientError("Persistent failure")
    
    mgr._safe_run_job("test_dlq_job", always_fail)
    
    mock_enqueue.assert_called_once()
    assert mock_enqueue.call_args[0][0] == "test_dlq_job"
    _reset_retry("test_dlq_job")


def test_safe_run_job_fatal_error_dlq(mocker):
    """Step 36: FatalError goes directly to DLQ without retry."""
    from scheduler import SchedulerManager, FatalError, _reset_retry
    
    mgr = SchedulerManager()
    mgr.scheduler = MagicMock()
    mgr._max_retries = 3
    _reset_retry("test_fatal_job")
    
    mock_enqueue = mocker.patch("scheduler.scheduler._enqueue_dlq")
    mock_sleep = mocker.patch("scheduler.scheduler.time.sleep")
    
    def always_fail():
        raise FatalError("Unrecoverable failure")
    
    mgr._safe_run_job("test_fatal_job", always_fail)
    
    mock_enqueue.assert_called_once()
    mock_sleep.assert_not_called()
    _reset_retry("test_fatal_job")


def test_safe_run_job_config_error_dlq(mocker):
    """Step 33: ConfigurationError goes to DLQ with notification."""
    from scheduler import SchedulerManager, ConfigurationError, _reset_retry
    
    mgr = SchedulerManager()
    mgr.scheduler = MagicMock()
    mgr._max_retries = 3
    _reset_retry("test_config_job")
    
    mock_enqueue = mocker.patch("scheduler.scheduler._enqueue_dlq")
    mock_sleep = mocker.patch("scheduler.scheduler.time.sleep")
    mock_notify = mocker.patch("scheduler.scheduler.notifier.notify_critical_error")
    
    def always_fail():
        raise ConfigurationError("Missing config")
    
    mgr._safe_run_job("test_config_job", always_fail)
    
    mock_enqueue.assert_called_once()
    mock_notify.assert_called_once()
    _reset_retry("test_config_job")


def test_compute_backoff():
    """Step 34: Exponential backoff with jitter."""
    import scheduler.scheduler as sched_mod
    
    original_random = sched_mod.random.uniform
    sched_mod.random.uniform = lambda a, b: 0.25
    
    try:
        assert sched_mod._compute_backoff(0) == 2.25
        assert sched_mod._compute_backoff(1) == 4.25
        assert sched_mod._compute_backoff(2) == 8.25
    finally:
        sched_mod.random.uniform = original_random


def test_enqueue_dlq(mocker, tmp_path):
    """Step 36: DLQ entry creation and file management."""
    import scheduler.scheduler as sched_mod
    
    test_path = tmp_path / "test_dlq.json"
    original_path = sched_mod._DEAD_LETTER_QUEUE_PATH
    sched_mod._DEAD_LETTER_QUEUE_PATH = test_path
    
    try:
        sched_mod._enqueue_dlq("test_job", "test error message")
        assert test_path.exists()
        
        with open(test_path) as f:
            entries = json.load(f)
        assert len(entries) == 1
        assert entries[0]["job_id"] == "test_job"
        assert entries[0]["error"] == "test error message"
    finally:
        sched_mod._DEAD_LETTER_QUEUE_PATH = original_path


def test_retry_dlq_jobs_empty(tmp_path):
    """Step 36: retry_dlq_jobs handles empty/nonexistent DLQ."""
    import scheduler.scheduler as sched_mod
    
    test_path = tmp_path / "nonexistent_dlq.json"
    original_path = sched_mod._DEAD_LETTER_QUEUE_PATH
    sched_mod._DEAD_LETTER_QUEUE_PATH = test_path
    
    try:
        result = sched_mod.retry_dlq_jobs()
        assert result["retried"] == 0
        assert result["failed"] == 0
    finally:
        sched_mod._DEAD_LETTER_QUEUE_PATH = original_path
