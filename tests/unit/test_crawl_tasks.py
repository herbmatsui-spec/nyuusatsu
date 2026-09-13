import pytest
from unittest.mock import MagicMock, patch

from job_queue.tasks.crawl_tasks import crawl_agency_task


class TestCrawlTasks:
    @pytest.fixture
    def mock_bid_source(self):
        """Mock BidSource object"""
        mock_source = MagicMock()
        mock_source.prefecture_id = 13
        return mock_source

    @pytest.fixture
    def mock_crawl_result(self):
        """Mock CrawlResult object"""
        mock_result = MagicMock()
        mock_result.bids_found = 150
        mock_result.bids_new = 25
        return mock_result

    def test_crawl_agency_task_success(self, mock_bid_source, mock_crawl_result):
        """正常なクロールタスク実行をテスト"""
        with patch('job_queue.tasks.crawl_tasks.SessionLocal') as mock_session_local, \
             patch('job_queue.tasks.crawl_tasks.CrawlScheduler') as mock_scheduler_class:
            
            # モックセッションの設定
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None
            
            # モッククエリの設定
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = mock_bid_source
            mock_session.query.return_value = mock_query
            
            # モック scheduler の設定
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            mock_scheduler.run_crawl_for_prefecture.return_value = mock_crawl_result
            
            # 関数の実行
            result = crawl_agency_task(agency_id=123)
            
            # 検証
            mock_session_local.assert_called_once()
            mock_session.query.assert_called_once()
            # Note: We're not checking the exact query arguments since BidSource is imported locally
            mock_scheduler_class.assert_called_once()
            mock_scheduler.run_crawl_for_prefecture.assert_called_once_with(13)
            
            assert result["status"] == "success"
            assert result["agency_id"] == 123
            assert result["bids_found"] == 150
            assert result["bids_new"] == 25

    def test_crawl_agency_task_no_bidsource(self):
        """BidSourceが見つからない場合のエラーハンドリングをテスト"""
        with patch('job_queue.tasks.crawl_tasks.SessionLocal') as mock_session_local:
            # モックセッションの設定
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None
            
            # モッククエリの設定 - BidSourceが見つからない場合
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = None
            mock_session.query.return_value = mock_query
            
            # 関数の実行
            result = crawl_agency_task(agency_id=999)
            
            # 検証
            mock_session_local.assert_called_once()
            mock_session.query.assert_called_once()
            
            assert result["status"] == "error"
            assert "Agency not found" in result["message"]

    def test_crawl_agency_task_exception_handling(self, mock_bid_source):
        """例外が発生した場合のエラーハンドリングをテスト"""
        with patch('job_queue.tasks.crawl_tasks.SessionLocal') as mock_session_local, \
             patch('job_queue.tasks.crawl_tasks.CrawlScheduler') as mock_scheduler_class:
            
            # モックセッションの設定
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            mock_session_local.return_value.__exit__.return_value = None
            
            # モッククエリの設定
            mock_query = MagicMock()
            mock_query.filter.return_value.first.retureturn_value.__exit__.return_value = None
            
            # モッククエリの設定
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = mock_bid_source
            mock_session.query.return_value = mock_query
            
            # モック scheduler の設定 - 例外を発生させる
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            mock_scheduler.run_crawl_for_prefecture.side_effect = Exception("Crawl failed")
            
            # 関数の実行と例外の検証
            with pytest.raises(Exception, match="Crawl failed"):
                crawl_agency_task(agency_id=123)
            
            # セッションが適切にクローズされることを確認
            mock_session_local.assert_called_once()