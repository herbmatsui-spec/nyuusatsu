import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.base import Base

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEST_DB_PATH = os.path.abspath(os.path.join(_BASE_DIR, "tests", "fixtures", "test.db"))
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

def setup_test_db():
    """テスト用データベースを作成し、スキーマを初期化する"""
    # 既存のテストDBを削除してクリーンな状態で開始
    if os.path.exists(TEST_DB_PATH):
        try:
            # ガベージコレクションで未クローズの接続ハンドル解放を期待
            import gc
            gc.collect()
            os.remove(TEST_DB_PATH)
        except PermissionError:
            pass
    
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine

def get_test_session():
    """テスト用のセッションを返す"""
    engine = setup_test_db()
    Session = sessionmaker(bind=engine)
    return Session()

if __name__ == "__main__":
    setup_test_db()
    print(f"Test database created at {TEST_DB_PATH}")
