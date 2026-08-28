import pytest
from unittest.mock import MagicMock, patch
from app_admin import app
from database.models.agency import Agency
from database.models.crawl_config import CrawlConfig
from database.models.crawl_log import CrawlLog

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.secret_key = "testsecret"
    with app.test_client() as client:
        yield client

def test_list_agencies(client, db_session, mocker):
    agency = Agency(name="テスト自治体Admin", type="municipality", region="東京都")
    db_session.add(agency)
    db_session.commit()

    config = CrawlConfig(
        agency_id=agency.id,
        target_url="https://example.com/admin_test.html",
        parser_type="heuristic",
        frequency="daily",
        is_active=True
    )
    db_session.add(config)
    db_session.commit()

    # SessionLocal をモック化して db_session を返すようにする
    mocker.patch("app_admin.SessionLocal", return_value=db_session)

    res = client.get("/agencies")
    assert res.status_code == 200
    assert b"test_list_agencies" not in res.data # ただのテスト名ノイズ除け
    assert b"admin_test.html" in res.data
    assert b"\xe3\x83\x86\xe3\x82\xb9\xe3\x83\x88\xe8\x87\xaa\xe6\xb2\xbb\xe4\xbd\x93Admin" in res.data # UTF-8 テスト自治体Admin

def test_toggle_agency(client, db_session, mocker):
    agency = Agency(name="トグル対象", type="municipality", region="東京都")
    db_session.add(agency)
    db_session.commit()

    config = CrawlConfig(
        agency_id=agency.id,
        target_url="https://example.com/toggle.html",
        parser_type="rss",
        frequency="daily",
        is_active=True
    )
    db_session.add(config)
    db_session.commit()

    mocker.patch("app_admin.SessionLocal", return_value=db_session)
    mock_sync = mocker.patch("app_admin.scheduler_manager.sync_crawl_jobs")

    res = client.post(f"/agencies/toggle/{config.id}", follow_redirects=True)
    assert res.status_code == 200

    # セッションがリクエスト内でクローズされた可能性があるため、新しくクエリして確認
    updated_config = db_session.query(CrawlConfig).filter(CrawlConfig.id == config.id).first()
    assert updated_config.is_active is False
    mock_sync.assert_called_once()

def test_run_agency_crawl_now(client, db_session, mocker):
    agency = Agency(name="即時実行対象", type="municipality", region="東京都")
    db_session.add(agency)
    db_session.commit()

    config = CrawlConfig(
        agency_id=agency.id,
        target_url="https://example.com/run.html",
        parser_type="rss",
        frequency="daily",
        is_active=True
    )
    db_session.add(config)
    db_session.commit()

    mocker.patch("app_admin.SessionLocal", return_value=db_session)
    mock_trigger = mocker.patch("crawler.pipeline.trigger_agency_crawl")

    res = client.post(f"/agencies/run/{config.id}", follow_redirects=True)
    assert res.status_code == 200
    mock_trigger.assert_called_once_with(config.id)


def test_view_agency_logs(client, db_session, mocker):
    agency = Agency(name="ログ閲覧対象", type="municipality", region="東京都")
    db_session.add(agency)
    db_session.commit()

    log = CrawlLog(
        agency_id=agency.id,
        status="failed",
        error_message="HTTP Timeout Error",
        new_bids_count=0
    )
    db_session.add(log)
    db_session.commit()

    mocker.patch("app_admin.SessionLocal", return_value=db_session)

    res = client.get(f"/agencies/logs/{agency.id}")
    assert res.status_code == 200
    assert b"FAILED" in res.data
    assert b"HTTP Timeout Error" in res.data
