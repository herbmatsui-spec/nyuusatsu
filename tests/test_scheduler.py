import pytest
from unittest.mock import MagicMock
from scheduler import SchedulerManager
from database.models.agency import Agency
from database.models.crawl_config import CrawlConfig

def test_sync_crawl_jobs(db_session, mocker):
    # テスト用の Agency と CrawlConfig を作成
    agency1 = Agency(name="自治体A", type="municipality", region="東京都")
    agency2 = Agency(name="自治体B", type="municipality", region="神奈川県")
    db_session.add_all([agency1, agency2])
    db_session.commit()

    config1 = CrawlConfig(agency_id=agency1.id, target_url="https://example.com/a.html", parser_type="heuristic", frequency="hourly", is_active=True)
    config2 = CrawlConfig(agency_id=agency2.id, target_url="https://example.com/b.html", parser_type="rss", frequency="daily", is_active=False) # 非アクティブ
    db_session.add_all([config1, config2])
    db_session.commit()

    # get_db コンテキストマネージャをモック化
    mock_get_db = mocker.patch("scheduler.get_db")
    mock_get_db.return_value.__enter__.return_value = db_session

    # trigger_agency_crawl をモック化
    mock_trigger = mocker.patch("scheduler.trigger_agency_crawl")

    # SchedulerManager のインスタンス化とモック化
    mgr = SchedulerManager()
    mgr.scheduler = MagicMock()

    # ジョブリストのモック
    mgr.scheduler.get_jobs.return_value = []

    # 実行
    mgr.sync_crawl_jobs()

    # アクティブな config1 のジョブが追加されたか検証（シードデータ等の他ジョブの呼び出しも考慮）
    job_id = f"agency_crawl_{config1.id}"
    
    # add_job が呼び出された引数リストを走査し、目的の job_id が含まれているか検証
    called_jobs = [call.kwargs.get('id') for call in mgr.scheduler.add_job.call_args_list]
    assert job_id in called_jobs


