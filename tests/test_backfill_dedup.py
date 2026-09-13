"""重複排除サービステスト"""
import pytest
from datetime import date, datetime
from unittest.mock import Mock, patch, MagicMock

from services.backfill_dedup import BackfillDedupService
from database.models import Bid


class TestBackfillDedupService:
    """BackfillDedupService のテスト"""

    def test_find_duplicates(self):
        """重複検出テスト"""
        service = BackfillDedupService()
        
        with patch.object(service, 'storage') as mock_storage:
            mock_db = MagicMock()
            
            # 重複グループを模倣
            dup_bids = [
                Mock(id=1, source_url="http://example.com/1"),
                Mock(id=2, source_url="http://example.com/1"),
                Mock(id=3, source_url="http://example.com/2"),
                Mock(id=4, source_url="http://example.com/2"),
                Mock(id=5, source_url="http://example.com/3"),  # 重複なし
            ]
            
            mock_db.query.return_value.filter.return_value.all.return_value = dup_bids
            
            with patch('services.backfill_dedup.get_db', return_value=iter([mock_db])):
                duplicates = service.find_duplicates()
            
            assert len(duplicates) == 2  # 2つの重複グループ
            assert "http://example.com/1" in duplicates
            assert "http://example.com/2" in duplicates
            assert len(duplicates["http://example.com/1"]) == 2
            assert len(duplicates["http://example.com/2"]) == 2

    def test_merge_duplicates_dry_run(self):
        """重複統合ドライランテスト"""
        service = BackfillDedupService()
        
        with patch.object(service, 'find_duplicates') as mock_find:
            mock_find.return_value = {
                "http://example.com/1": [
                    Mock(id=1, source_url="http://example.com/1", budget_amount=1000, updated_at=datetime(2024, 1, 2)),
                    Mock(id=2, source_url="http://example.com/1", budget_amount=None, updated_at=datetime(2024, 1, 1)),
                ]
            }
            
            result = service.merge_duplicates(dry_run=True)
            
            assert result["merged"] == 1
            assert result["deleted"] == 0

    def test_merge_duplicates_execute(self):
        """重複統合実行テスト"""
        service = BackfillDedupService()
        
        with patch.object(service, 'find_duplicates') as mock_find:
            with patch('services.backfill_dedup.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = iter([mock_db])
                
                bid1 = Mock(id=1, source_url="http://example.com/1", budget_amount=1000, updated_at=datetime(2024, 1, 2))
                bid2 = Mock(id=2, source_url="http://example.com/1", budget_amount=None, updated_at=datetime(2024, 1, 1))
                
                mock_find.return_value = {
                    "http://example.com/1": [bid1, bid2]
                }
                
                result = service.merge_duplicates(dry_run=False)
                
                assert result["merged"] == 1
                assert result["deleted"] == 1
                mock_db.delete.assert_called_once_with(bid2)
                mock_db.commit.assert_called_once()

    def test_clean_orphans(self):
        """孤立レコードクリーンアップテスト"""
        service = BackfillDedupService()
        
        with patch('services.backfill_dedup.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            
            orphan_bids = [Mock(id=1), Mock(id=2)]
            mock_db.query.return_value.filter.return_value.all.return_value = orphan_bids
            
            count = service.clean_orphans(dry_run=False)
            
            assert count == 2
            assert mock_db.delete.call_count == 2
            mock_db.commit.assert_called_once()

    def test_check_integrity(self):
        """整合性チェックテスト"""
        service = BackfillDedupService()
        
        with patch.object(service, 'find_duplicates') as mock_find:
            with patch('services.backfill_dedup.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = iter([mock_db])
                
                mock_find.return_value = {"url1": [Mock(), Mock()]}
                
                mock_db.query.return_value.filter.return_value.count.side_effect = [5, 3, 2, 1]
                
                result = service.check_integrity()
                
                assert "duplicate_groups" in result
                assert "duplicate_total" in result
                assert "null_source_url" in result
                assert "missing_budget_amount" in result
                assert "missing_announcement_date" in result
                assert "missing_organization_name" in result

    def test_detect_anomalies(self):
        """異常値検出テスト"""
        service = BackfillDedupService()
        
        with patch('services.backfill_dedup.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            
            # 正常値と異常値を含むデータ
            bids = [
                Mock(id=1, budget_amount=1000000),      # 正常
                Mock(id=2, budget_amount=100),          # 異常（小さすぎ）
                Mock(id=3, budget_amount=100000000000), # 異常（大きすぎ）
                Mock(id=4, announcement_date=date(2024, 1, 1)),  # 正常
                Mock(id=5, announcement_date=date(1900, 1, 1)),  # 異常（古すぎ）
                Mock(id=6, announcement_date=date(2030, 1, 1)),  # 異常（未来すぎ）
            ]
            mock_db.query.return_value.filter.return_value.all.return_value = bids
            
            result = service.detect_anomalies()
            
            assert "budget_amount" in result
            assert len(result["budget_amount"]) == 2
            assert "announcement_date" in result
            assert len(result["announcement_date"]) == 2

    def test_backfill_missing_fields(self):
        """欠落フィールド補完テスト"""
        service = BackfillDedupService()
        
        with patch('services.backfill_dedup.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])
            
            job = Mock(id=1, start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
            mock_db.query.return_value.get.return_value = job
            
            bid = Mock(
                id=1, 
                budget="1,000,000円",
                budget_amount=None,
                announcement_date=None,
                organization_name="  株式会社テスト  ",
                deadline=None,
                created_at=datetime(2024, 6, 1),
                updated_at=datetime(2024, 6, 1),
            )
            mock_db.query.return_value.filter.return_value.all.return_value = [bid]
            
            # _extract_budget_amount のモック
            service.storage._extract_budget_amount = Mock(return_value=1000000)
            
            result = service.backfill_missing_fields(job_id=1, dry_run=True)
            
            assert "budget_amount" in result
            assert "organization_name_normalized" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])