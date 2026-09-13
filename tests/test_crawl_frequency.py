#!/usr/bin/env python3
"""Unit tests for dynamic crawl frequency adjustment."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch

import sys
sys.path.insert(0, '/home/herbmatsui/nyuusatsu')

from scripts.adjust_crawl_frequency import (
    get_default_base_interval,
    adjust_interval,
    calculate_success_rate,
    upsert_schedule,
    initialize_default_schedules,
)
from scripts.report_crawl_success import calculate_success_rate as report_calculate_success_rate


class TestAdjustInterval:
    """Tests for interval adjustment logic."""

    def test_high_success_rate_shortens_interval(self):
        """High success rate should shorten interval toward target."""
        base = 3600
        current = 3600
        success_rate = 1.0  # 100%
        target = 0.95

        new_interval = adjust_interval(base, current, success_rate, target)
        # ratio = 0.95/1.0 = 0.95, new = 3600 * 0.95 = 3420
        assert new_interval == 3420

    def test_target_success_rate_keeps_base(self):
        """At target success rate, interval should equal base."""
        base = 3600
        current = 5000
        success_rate = 0.95
        target = 0.95

        new_interval = adjust_interval(base, current, success_rate, target)
        assert new_interval == 3600

    def test_low_success_rate_lengthens_interval(self):
        """Low success rate should lengthen interval."""
        base = 3600
        current = 3600
        success_rate = 0.5  # 50%
        target = 0.95

        new_interval = adjust_interval(base, current, success_rate, target)
        # ratio = 0.95/0.5 = 1.9, new = 3600 * 1.9 = 6840
        assert new_interval == 6840

    def test_zero_success_rate_doubles_interval(self):
        """Zero success rate should double interval (capped at max)."""
        base = 3600
        current = 3600
        success_rate = 0.0

        new_interval = adjust_interval(base, current, success_rate)
        # Should double current, capped at MAX_INTERVAL (86400)
        assert new_interval == 7200

    def test_min_interval_bound(self):
        """Interval should not go below MIN_INTERVAL (300s)."""
        base = 100  # Very small base
        current = 100
        success_rate = 1.0

        new_interval = adjust_interval(base, current, success_rate)
        assert new_interval >= 300

    def test_max_interval_bound(self):
        """Interval should not exceed MAX_INTERVAL (86400s)."""
        base = 50000
        current = 50000
        success_rate = 0.1  # Very low

        new_interval = adjust_interval(base, current, success_rate)
        assert new_interval <= 86400


class TestDefaultBaseInterval:
    """Tests for default base interval by priority."""

    def test_priority_1(self):
        assert get_default_base_interval(1) == 1800

    def test_priority_2(self):
        assert get_default_base_interval(2) == 3600

    def test_priority_3(self):
        assert get_default_base_interval(3) == 7200

    def test_priority_4(self):
        assert get_default_base_interval(4) == 14400

    def test_priority_5(self):
        assert get_default_base_interval(5) == 28800

    def test_unknown_priority(self):
        assert get_default_base_interval(10) == 3600
        assert get_default_base_interval(0) == 3600


class TestCalculateSuccessRate:
    """Tests for success rate calculation."""

    @patch('scripts.adjust_crawl_frequency.get_session')
    def test_no_agencies_returns_default(self, mock_get_session):
        """No agencies in category/priority returns default success rate."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_get_session.return_value.__enter__.return_value = mock_session

        total, success, rate = calculate_success_rate(mock_session, 999, 1)
        assert total == 0
        assert success == 0
        assert rate == 1.0

    @patch('scripts.adjust_crawl_frequency.get_session')
    def test_crawl_logs_used_when_available(self, mock_get_session):
        """CrawlLog data is used when available."""
        mock_session = MagicMock()

        # Mock agencies
        mock_agency = Mock()
        mock_agency.id = 1
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_agency]

        # Mock crawl logs
        mock_log1 = Mock()
        mock_log1.status = "success"
        mock_log2 = Mock()
        mock_log2.status = "failed"
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_log1, mock_log2]

        total, success, rate = calculate_success_rate(mock_session, 1, 1)
        assert total == 2
        assert success == 1
        assert rate == 0.5

    @patch('scripts.adjust_crawl_frequency.get_session')
    def test_backfill_fallback_when_no_crawl_logs(self, mock_get_session):
        """BackfillJob is used when no CrawlLog entries."""
        mock_session = MagicMock()

        # Mock agencies - the code uses session.query(Agency.id) which is a column query
        mock_agency_id = Mock()
        mock_agency_id.id = 1
        mock_agency_query = MagicMock()
        mock_agency_query.filter.return_value.all.return_value = [mock_agency_id]

        # Mock crawl logs (empty)
        mock_crawl_log_query = MagicMock()
        mock_crawl_log_query.filter.return_value.all.return_value = []

        # Mock backfill jobs
        mock_backfill_query = MagicMock()
        mock_job1 = Mock()
        mock_job1.status = "done"
        mock_job2 = Mock()
        mock_job2.status = "failed"
        mock_backfill_query.filter.return_value.all.return_value = [mock_job1, mock_job2]

        # Set up query to return different mocks based on what's passed
        def query_side_effect(*args, **kwargs):
            # args[0] could be Agency.id (column) or CrawlLog class or BackfillJob class
            if args and hasattr(args[0], '__name__'):
                model_name = args[0].__name__
                if model_name == 'CrawlLog':
                    return mock_crawl_log_query
                elif model_name == 'BackfillJob':
                    return mock_backfill_query
            # For Agency.id column query
            return mock_agency_query

        mock_session.query.side_effect = query_side_effect

        total, success, rate = calculate_success_rate(mock_session, 1, 1)
        assert total == 2
        assert success == 1
        assert rate == 0.5


class TestUpsertSchedule:
    """Tests for schedule upsert."""

    @patch('scripts.adjust_crawl_frequency.get_session')
    def test_insert_new_schedule(self, mock_get_session):
        """Insert creates new schedule when none exists."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        schedule = upsert_schedule(mock_session, 1, 1, 3600, 3420, 0.95)

        assert schedule.category_id == 1
        assert schedule.priority_level == 1
        assert schedule.base_interval_seconds == 3600
        assert schedule.current_interval_seconds == 3420
        assert schedule.success_rate == 0.95
        mock_session.add.assert_called_once()

    @patch('scripts.adjust_crawl_frequency.get_session')
    def test_update_existing_schedule(self, mock_get_session):
        """Update modifies existing schedule."""
        mock_session = MagicMock()
        existing = Mock()
        existing.category_id = 1
        existing.priority_level = 1
        existing.base_interval_seconds = 3600
        existing.current_interval_seconds = 3600
        existing.success_rate = 1.0
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        schedule = upsert_schedule(mock_session, 1, 1, 3600, 3420, 0.95)

        assert schedule.current_interval_seconds == 3420
        assert schedule.success_rate == 0.95
        assert schedule.base_interval_seconds == 3600
        mock_session.add.assert_not_called()


class TestReportCalculateSuccessRate:
    """Tests for report script's calculate_success_rate."""

    @patch('scripts.report_crawl_success.get_session')
    def test_returns_dict_with_all_fields(self, mock_get_session):
        """Report calculate returns dict with all expected fields."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []

        result = report_calculate_success_rate(mock_session, 1, 1)

        assert "total_attempts" in result
        assert "successful_attempts" in result
        assert "success_rate" in result
        assert "avg_response_time_ms" in result
        assert "failed_attempts" in result
        assert result["total_attempts"] == 0
        assert result["success_rate"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])