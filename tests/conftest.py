import sys
import os
import json
from unittest.mock import MagicMock, patch

# プロジェクトルートを sys.path に追加（Cwd が C: ドライブの場合に必要）
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest
_DB_PATH = os.path.abspath(os.path.join(_PROJECT_ROOT, "tests", "fixtures", "test.db"))
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
from tests.fixtures.db_setup import setup_test_db, TEST_DATABASE_URL
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """テストセッション開始時に一度だけDBをセットアップする"""
    setup_test_db()

@pytest.fixture
def db_session():
    """各テストケースごとに新しいセッションを提供し、終了後にロールバックする"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def mock_session():
    """HTTPセッションのモックを提供"""
    from tests.mocks.extended_mocks import MockSession
    return MockSession()

@pytest.fixture
def mock_llm():
    """LLM APIのモックを提供"""
    from tests.mocks.extended_mocks import mock_llm_api_call
    return mock_llm_api_call

# Additional fixtures for enhanced testing capabilities

@pytest.fixture
def sample_html_content():
    """サンプルHTMLコンテンツを提供"""
    return """
    <html>
    <head><title>入札情報サンプル</title></head>
    <body>
        <h1>入札公告</h1>
        <div class="budget">予算額：1,000,000円</div>
        <div class="deadline">締切日：2024年12月31日</div>
        <div class="qualifications">【参加資格】東京都内に本店を有する法人であること。</div>
        <div class="announcement-date">公告日：令和6年7月10日</div>
        <a href="sample.pdf">仕様書ダウンロード</a>
    </body>
    </html>
    """

@pytest.fixture
def sample_json_response():
    """サンプルJSONレスポンスを提供"""
    return {
        "success": True,
        "data": {
            "bid_id": "BID-2024-001",
            "title": "システム開発入札",
            "budget": "1000000",
            "deadline": "2024-12-31"
        }
    }

@pytest.fixture
def mock_requests_get():
    """requests.getのモックを提供"""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Mock HTML</body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        yield mock_get

@pytest.fixture
def mock_requests_post():
    """requests.postのモックを提供"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        yield mock_post

@pytest.fixture
def temp_file(tmp_path):
    """一時ファイルを提供するファクトリー"""
    def _create_file(content="", suffix=".txt"):
        file_path = tmp_path / f"test_file{suffix}"
        file_path.write_text(content, encoding="utf-8")
        return file_path
    return _create_file

@pytest.fixture
def assert_raises_message():
    """特定のメッセージを含む例外が発生することをアサートするヘルパー"""
    def _assert_raises_message(expected_exception, expected_message, callable_obj, *args, **kwargs):
        with pytest.raises(expected_exception) as exc_info:
            callable_obj(*args, **kwargs)
        assert expected_message in str(exc_info.value)
    return _assert_raises_message
