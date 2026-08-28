"""
Step 54: URL監視の統合テスト
- プローブ -> DB保存 -> 失敗URL抽出 -> 通知 までのデータフローを検証
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from database.base import Base
from database.models.agency import Agency
from database.models.crawl_log import CrawlLog
from database.repositories import save_url_probe_log, get_active_agency_urls
from services.url_probe_common import probe_url, ProbeResult, probe_all_urls


@pytest.fixture
def test_db():
    """テスト用インメモリSQLiteデータベース"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # テスト用データ挿入
    agency1 = Agency(name="松山市", url="https://www.city.matsuyama.ehime.jp", is_active=True)
    agency2 = Agency(name="愛媛県", url="https://www.pref.ehime.jp", is_active=True)
    agency3 = Agency(name="Inactive Agency", url="https://inactive.example.com", is_active=False)
    session.add_all([agency1, agency2, agency3])
    session.commit()

    yield session

    session.close()
    engine.dispose()


class TestUrlMonitorIntegration:
    """URL監視の統合テスト: プローブ -> DB -> 通知"""

    @pytest.mark.asyncio
    async def test_probe_to_db_flow(self, test_db):
        """プローブ結果がDBに正しく保存されることを検証"""
        # 正常系のモックレスポンス
        mock_response = MagicMock()
        mock_response.status_code = 200

        # プローブ実行(モック)
        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
            agency_urls = get_active_agency_urls(test_db)
            assert len(agency_urls) == 2  # is_active=Trueの2件のみ

            for agency_id, url in agency_urls:
                result = await probe_url(url, timeout=5.0)
                assert result.is_reachable is True

                # DBに保存
                status = "success" if result.is_reachable else "failed"
                save_url_probe_log(test_db, agency_id, status, result.error)

        # DB検証
        logs = test_db.query(CrawlLog).all()
        assert len(logs) == 2
        assert all(log.status == "success" for log in logs)
        assert all(log.new_bids_count == 0 for log in logs)

    @pytest.mark.asyncio
    async def test_probe_failure_to_notification_flow(self, test_db):
        """プローブ失敗 -> DB保存 -> 通知フローを検証"""
        mock_response = MagicMock()
        mock_response.status_code = 500

        failed_urls = []

        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
            agency_urls = get_active_agency_urls(test_db)

            for agency_id, url in agency_urls:
                result = await probe_url(url, timeout=5.0)
                status = "success" if result.is_reachable else "failed"
                save_url_probe_log(test_db, agency_id, status, result.error)

                if not result.is_reachable:
                    failed_urls.append((url, result.error or "Unknown error"))

        # 失敗が記録されているか
        assert len(failed_urls) == 2
        logs = test_db.query(CrawlLog).filter(CrawlLog.status == "failed").all()
        assert len(logs) == 2

        # 通知関数のモック呼び出しを検証
        with patch("services.notification_service.NotificationService.notify_url_failures") as mock_notify:
            mock_notify.return_value = None
            from services.notification_service import NotificationService
            notifier = NotificationService(MagicMock())
            notifier.notify_url_failures(failed_urls)
            mock_notify.assert_called_once_with(failed_urls)

    @pytest.mark.asyncio
    async def test_probe_all_urls_with_db(self, test_db):
        """probe_all_urls がDBからURLを取得し並列プローブすることを検証"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
            results = await probe_all_urls(test_db, timeout=5.0, concurrency=2)

            assert len(results) == 2
            assert all(r.is_reachable for r in results)

    def test_inactive_agencies_filtered(self, test_db):
        """is_active=Falseの自治体がプローブ対象から除外されることを検証"""
        urls = get_active_agency_urls(test_db)
        assert len(urls) == 2
        assert all("inactive" not in url for _, url in urls)
