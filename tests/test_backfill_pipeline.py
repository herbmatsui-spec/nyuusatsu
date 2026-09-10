"""バックフィルパイプライン統合テスト"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from services.backfill_service import BackfillService
from services.backfill_dedup import BackfillDedupService
from database.models import BackfillJob, BackfillJobStatus, Agency, AgencyCategory


class TestBackfillPipeline:
    """バックフィルパイプライン全体の統合テスト"""

    def test_create_job_then_run_job_flow(self):
        """ジョブ作成 → 実行の流れテスト"""
        from database.session import get_db
        from database.models import Agency, AgencyCategory
        
        db = next(get_db())
        
        # テスト用機関作成
        cat = db.query(AgencyCategory).filter(AgencyCategory.name == 'prefecture').first()
        if not cat:
            cat = AgencyCategory(name='prefecture', priority=1)
            db.add(cat)
            db.flush()
        
        agency = Agency(
            name='Integration Test Agency',
            type='prefecture',
            category_id=cat.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(agency)
        db.flush()
        agency_id = agency.id
        
        try:
            service = BackfillService()
            
            # 1. ジョブ作成
            job = service.create_job(agency_id=agency_id, years=1)
            assert job.id is not None
            assert job.status == BackfillJobStatus.PENDING
            job_id = job.id
            
            # 2. ジョブ取得確認
            retrieved = service.get_job(job_id)
            assert retrieved.id == job_id
            assert retrieved.agency_id == agency_id
            
            # 3. クローラー実行をモックして run_job テスト
            with patch.object(service, '_get_crawler_for_agency') as mock_get_crawler:
                mock_crawler = Mock()
                mock_crawler.start_date = None
                mock_crawler.end_date = None
                mock_get_crawler.return_value = mock_crawler
                
                with patch.object(service, '_run_crawl') as mock_run_crawl:
                    mock_run_crawl.return_value = [
                        {
                            "title": "Test Bid",
                            "organization": "Test Agency",
                            "budget": "1,000,000円",
                            "deadline": "2024-12-31",
                            "source_url": "http://example.com/bid/1",
                            "project_name": "Test Bid",
                            "prefecture_code": "01",
                            "announcement_date": date.today(),
                        }
                    ]
                    
                    with patch.object(service.storage, 'save_bid') as mock_save_bid:
                        mock_bid = Mock()
                        mock_bid.created_at = datetime.utcnow()
                        mock_bid.updated_at = datetime.utcnow()
                        mock_save_bid.return_value = mock_bid
                        
                        # 実行
                        completed_job = service.run_job(job_id)
                        
                        assert completed_job.status == BackfillJobStatus.DONE
                        assert completed_job.fetched_count == 1
                        assert completed_job.new_count == 1
                        assert completed_job.error_count == 0
                        assert completed_job.finished_at is not None
            
        finally:
            # クリーンアップ
            db.query(BackfillJob).filter(BackfillJob.id == job_id).delete()
            db.delete(agency)
            db.commit()
        
        db.close()

    def test_full_backfill_cycle_with_dedup(self):
        """バックフィル実行 → 重複排除のサイクルテスト"""
        service = BackfillService()
        dedup = BackfillDedupService()
        
        # ジョブ作成
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            job = service.create_job(agency_id=1, years=1)
            job_id = job.id
        
        # 重複排除実行（ドライラン）
        with patch.object(dedup, 'find_duplicates', return_value={}):
            result = dedup.merge_duplicates(dry_run=True)
            assert result["merged"] == 0
            assert result["deleted"] == 0
        
        # 整合性チェック
        with patch.object(dedup, 'find_duplicates', return_value={}):
            with patch('services.backfill_dedup.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = iter([mock_db])
                mock_db.query.return_value.filter.return_value.count.return_value = 0
                
                integrity = dedup.check_integrity()
                assert "duplicate_groups" in integrity
                assert integrity["duplicate_groups"] == 0

    def test_job_retry_after_failure(self):
        """失敗ジョブのリトライテスト"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            job = Mock()
            job.id = 1
            job.status = BackfillJobStatus.FAILED
            job.retry_count = 0
            mock_db.query.return_value.get.return_value = job
            
            service.run_job = Mock(return_value=Mock())
            
            # リトライ実行
            service.retry_job(1)
            
            assert job.status == BackfillJobStatus.PENDING
            assert job.retry_count == 1
            service.run_job.assert_called_once_with(1)

    def test_notification_on_completion(self):
        """完了時の通知テスト"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            job = Mock()
            job.id = 1
            job.agency_id = 1
            job.status = BackfillJobStatus.RUNNING
            job.started_at = datetime.utcnow()
            mock_db.query.return_value.get.return_value = job
            
            agency = Mock()
            agency.name = "Test Agency"
            mock_db.query.return_value.get.return_value = agency
            
            with patch.object(service, '_get_crawler_for_agency') as mock_get_crawler:
                mock_crawler = Mock()
                mock_get_crawler.return_value = mock_crawler
                
                with patch.object(service, '_run_crawl') as mock_run_crawl:
                    mock_run_crawl.return_value = []
                    
                    with patch('services.backfill_service.notify_backfill_done') as mock_notify:
                        completed_job = service.run_job(1)
                        
                        assert completed_job.status == BackfillJobStatus.DONE
                        mock_notify.assert_called_once()

    def test_cancel_running_job(self):
        """実行中ジョブのキャンセルテスト"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            job = Mock()
            job.id = 1
            job.agency_id = 1
            job.status = BackfillJobStatus.RUNNING
            mock_db.query.return_value.get.return_value = job
            
            agency = Mock()
            agency.name = "Test Agency"
            mock_db.query.return_value.get.return_value = agency
            
            with patch('services.backfill_service.notify_backfill_error') as mock_notify:
                cancelled_job = service.cancel_job(1)
                
                assert cancelled_job.status == BackfillJobStatus.FAILED
                assert cancelled_job.error_message == "Cancelled by user"
                mock_notify.assert_called_once()


class TestBackfillEdgeCases:
    """エッジケースのテスト"""

    def test_create_job_with_custom_dates(self):
        """カスタム日付でのジョブ作成"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            start = date(2023, 1, 1)
            end = date(2023, 12, 31)
            job = service.create_job(agency_id=1, start_date=start, end_date=end)
            
            assert job.start_date == start
            assert job.end_date == end

    def test_create_job_duplicate_pending_skipped(self):
        """PENDING ジョブとの重複はスキップ"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            existing = Mock()
            existing.id = 1
            existing.status = BackfillJobStatus.PENDING
            mock_db.query.return_value.filter.return_value.first.return_value = existing
            
            job = service.create_job(agency_id=1, years=1)
            assert job.id == 1
            mock_db.add.assert_not_called()

    def test_create_job_duplicate_running_skipped(self):
        """RUNNING ジョブとの重複はスキップ"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            existing = Mock()
            existing.id = 2
            existing.status = BackfillJobStatus.RUNNING
            mock_db.query.return_value.filter.return_value.first.return_value = existing
            
            job = service.create_job(agency_id=1, years=1)
            assert job.id == 2

    def test_list_jobs_with_filters(self):
        """フィルタ付きジョブ一覧"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            query_mock = MagicMock()
            mock_db.query.return_value = query_mock
            query_mock.filter.return_value = query_mock
            query_mock.order_by.return_value = query_mock
            query_mock.limit.return_value.all.return_value = []
            
            service.list_jobs(agency_id=1, status=BackfillJobStatus.DONE, limit=50)
            
            assert query_mock.filter.call_count >= 2
            query_mock.limit.assert_called_once_with(50)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])