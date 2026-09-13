"""BackfillService 単体テスト"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock, PropertyMock

from services.backfill_service import BackfillService
from database.models import BackfillJob, BackfillJobStatus, Agency, AgencyCategory


class TestBackfillService:
    """BackfillService の単体テスト"""

    def test_create_job_basic(self):
        """基本的なジョブ作成テスト"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            # 重複チェックで既存ジョブなし
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            # 作成されるジョブのモック
            mock_job = MagicMock(spec=BackfillJob)
            mock_job.agency_id = 1
            mock_job.status = BackfillJobStatus.PENDING
            mock_job.fetched_count = 0
            mock_job.new_count = 0
            mock_job.updated_count = 0
            mock_job.error_count = 0
            mock_job.retry_count = 0
            
            # add された時にモックジョブを返すようにする
            def add_side_effect(obj):
                if isinstance(obj, BackfillJob):
                    obj.id = 1
                    obj.status = BackfillJobStatus.PENDING
                    obj.fetched_count = 0
                    obj.new_count = 0
                    obj.updated_count = 0
                    obj.error_count = 0
                    obj.retry_count = 0
            mock_db.add.side_effect = add_side_effect
            
            job = service.create_job(agency_id=1, years=2)
            
            assert job.agency_id == 1
            assert job.status == BackfillJobStatus.PENDING
            mock_db.add.assert_called_once()
            mock_db.flush.assert_called_once()

    def test_create_job_duplicate_skipped(self):
        """重複ジョブはスキップされる"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            # 既存ジョブあり
            existing_job = Mock()
            existing_job.id = 999
            existing_job.status = BackfillJobStatus.PENDING
            mock_db.query.return_value.filter.return_value.first.return_value = existing_job
            
            job = service.create_job(agency_id=1, years=2)
            
            assert job.id == 999
            mock_db.add.assert_not_called()

    def test_get_job(self):
        """ジョブ取得テスト"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            job = Mock()
            job.id = 1
            mock_db.query.return_value.get.return_value = job
            
            result = service.get_job(1)
            
            assert result == job
            mock_db.expunge.assert_called_once_with(job)

    def test_list_jobs(self):
        """ジョブ一覧取得テスト"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            job1 = Mock()
            job1.id = 1
            job2 = Mock()
            job2.id = 2
            
            query_mock = MagicMock()
            mock_db.query.return_value = query_mock
            query_mock.filter.return_value = query_mock
            query_mock.order_by.return_value = query_mock
            query_mock.limit.return_value.all.return_value = [job1, job2]
            
            result = service.list_jobs(agency_id=1, status=BackfillJobStatus.PENDING)
            
            assert len(result) == 2
            assert mock_db.expunge.call_count == 2

    def test_retry_job_success(self):
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
            
            # run_job をモック
            service.run_job = Mock(return_value=Mock())
            
            result = service.retry_job(1)
            
            assert job.status == BackfillJobStatus.PENDING
            assert job.retry_count == 1
            assert job.error_message is None
            service.run_job.assert_called_once_with(1)

    def test_retry_job_invalid_status(self):
        """無効ステータスでのリトライはエラー"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            job = Mock()
            job.status = BackfillJobStatus.DONE
            mock_db.query.return_value.get.return_value = job
            
            with pytest.raises(ValueError, match="Cannot retry job with status: done"):
                service.retry_job(1)

    def test_cancel_job_success(self):
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
            
            # Agency もモック
            agency = Mock()
            agency.name = "Test Agency"
            # 2回目の get 呼び出しで agency を返す
            mock_db.query.return_value.get.side_effect = [job, agency]
            
            with patch('services.backfill_service.notify_backfill_error') as mock_notify:
                result = service.cancel_job(1)
                
                assert job.status == BackfillJobStatus.FAILED
                assert job.error_message == "Cancelled by user"
                assert job.finished_at is not None
                mock_notify.assert_called_once()

    def test_cancel_job_invalid_status(self):
        """RUNNING 以外のキャンセルはエラー"""
        service = BackfillService()
        
        with patch.object(service, '_session') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            job = Mock()
            job.status = BackfillJobStatus.PENDING
            mock_db.query.return_value.get.return_value = job
            
            with pytest.raises(ValueError, match="Cannot cancel job with status: pending"):
                service.cancel_job(1)


class TestBackfillServiceIntegration:
    """統合的なテスト（モックなし）"""

    def test_create_and_get_job(self):
        """ジョブ作成と取得の統合テスト"""
        from database.session import get_db
        from database.models import Agency, AgencyCategory, BackfillJobStatus
        
        db = next(get_db())
        
        # テスト用機関作成
        cat = db.query(AgencyCategory).filter(AgencyCategory.name == 'prefecture').first()
        if not cat:
            cat = AgencyCategory(name='prefecture', priority=1)
            db.add(cat)
            db.flush()
        
        agency = Agency(
            name='Test Agency',
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
            
            # ジョブ作成
            job = service.create_job(agency_id=agency_id, years=1)
            assert job.agency_id == agency_id
            assert job.status == BackfillJobStatus.PENDING
            assert job.start_date <= date.today()
            assert job.end_date >= date.today()
            
            # ジョブ取得
            retrieved = service.get_job(job.id)
            assert retrieved.id == job.id
            assert retrieved.agency_id == agency_id
            
            # 重複作成はスキップ
            job2 = service.create_job(agency_id=agency_id, years=1)
            assert job2.id == job.id
            
        finally:
            # クリーンアップ
            db.query(BackfillJob).filter(BackfillJob.id == job.id).delete()
            db.delete(agency)
            db.commit()
        
        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])