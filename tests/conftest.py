import sys
import os

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
