# 低性能LLM向け実装計画書 P1: DB統合と基盤改善 (ステップ 1-24)

## 概要
低性能なLLMでも実装可能なように、DB統合と基盤改善を極小ステップに分割しました。各ステップは5-10行程度の変更で完了します。

---

## ステップ 1-6: db_manager.py の基本構造変更

### ステップ 1: ファイルのバックアップ作成
- `db_manager.py` を `db_manager.py.backup` にコピーする

### ステップ 2: SQLAlchemy インポート追加
- ファイル冒頭に `from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text` を追加
- ファイル冒頭に `from sqlalchemy.ext.declarative import declarative_base` を追加
- ファイル冒頭に `from sqlalchemy.orm import sessionmaker` を追加

### ステップ 3: Base クラス定義追加
- インポート後の行に `Base = declarative_base()` を追加

### ステップ 4: CrawlHistory モデル定義追加
- Base クラス定義後に以下を追加:
```python
class CrawlHistory(Base):
    __tablename__ = 'crawl_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    crawl_time = Column(DateTime, nullable=False)
    url_count = Column(Integer, nullable=False)
    new_count = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)
```

### ステップ 5: CrawledUrl モデル定義追加
- CrawlHistory クラス後に以下を追加:
```python
class CrawledUrl(Base):
    __tablename__ = 'crawled_urls'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), unique=True, nullable=False)
    title = Column(String(500), nullable=True)
    found_time = Column(DateTime, nullable=False)
    notified = Column(Boolean, default=False)
```

### ステップ 6: Settings モデル定義追加
- CrawledUrl クラス後に以下を追加:
```python
class Settings(Base):
    __tablename__ = 'settings'
    
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
```

---

## ステップ 7-12: データベースエンジンとセッション設定

### ステップ 7: データベースパス定義変更
- 既存の `DB_PATH = os.path.join("data", "crawl_history.db")` を
  `DATABASE_URL = "sqlite:///" + os.path.join("data", "crawl_history.db")` に変更

### ステップ 8: エンジン作成関数追加
- モデル定義後に以下を追加:
```python
def get_engine():
    return create_engine(DATABASE_URL, echo=False)
```

### ステップ 9: セッションメーカー作成関数追加
- get_engine 関数後に以下を追加:
```python
def get_session_local():
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

### ステップ 10: テーブル作成関数追加
- get_session_local 関数後に以下を追加:
```python
def init_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
```

### ステップ 11: セッション取得関数追加
- init_db 関数後に以下を追加:
```python
def get_db():
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()
```

### ステップ 12: 既存関数のインターフェース変更準備
- `record_crawl_history` 関数の直前に `# TODO: この関数は後でORMベースに置き換える` コメントを追加

---

## ステップ 13-18: 既存関数の段階的置き換え

### ステップ 13: record_crawl_history 関数の置き換え準備
- 関数の最初に `# ORMベースの実装に置き換える予定` コメントを追加

### ステップ 14: record_crawl_history 関数のORM実装（準備段階）
- 関数内部のSQL実行をコメントアウトし、代わりにプレースホルダーを追加:
```python
# TODO: ORM実装に置き換える
# conn = sqlite3.connect(DB_PATH)
# cursor = conn.cursor()
# ... 既存のSQLコードをコメントアウト
pass  # 一時的に何もしない
```

### ステップ 15: get_crawl_history 関数の置き換え準備
- 関数の最初に `# ORMベースの実装に置き換える予定` コメントを追加

### ステップ 16: get_crawl_history 関数のORM実装（準備段階）
- 関数内部のSQL実行をコメントアウトし、代わりにプレースホルダーを追加:
```python
# TODO: ORM実装に置き換える
# conn = sqlite3.connect(DB_PATH)
# cursor = conn.cursor()
# ... 既存のSQLコードをコメントアウト
return []  # 一時的に空リストを返す
```

### ステップ 17: テスト用インポート文追加
- ファイル末尾の `if __name__ == "__main__":` ブロックの前に
  `from sqlalchemy.orm import Session` を追加

### ステップ 18: 基本動作テスト用コード追加
- `if __name__ == "__main__":` ブロック内の既存コードを保持し、
  その前に `init_db()` を呼び出す行を追加

---

## ステップ 19-24: テストと検証

### ステップ 19: インポートテスト用スクリプト作成
- `test_db_import.py` ファイルを作成し、以下を追加:
```python
from db_manager import get_engine, Base
print("Import test passed")
```

### ステップ 20: モデル定義テスト用スクリプト作成
- `test_db_models.py` ファイルを作成し、以下を追加:
```python
from db_manager import Base, CrawlHistory, CrawledUrl, Settings
print(f"Models: {Base.metadata.tables.keys()}")
```

### ステップ 21: エンジン作成テスト用スクリプト作成
- `test_db_engine.py` ファイルを作成し、以下を追加:
```python
from db_manager import get_engine
engine = get_engine()
print(f"Engine: {engine.url}")
```

### ステップ 22: テーブル作成テスト用スクリプト作成
- `test_db_create_tables.py` ファイルを作成し、以下を追加:
```python
from db_manager import init_db
init_db()
print("Tables created")
```

### ステップ 23: セッション作成テスト用スクリプト作成
- `test_db_session.py` ファイルを作成し、以下を追加:
```python
from db_manager import get_session_local
SessionLocal = get_session_local()
print(f"SessionLocal: {SessionLocal}")
```

### ステップ 24: 統合テスト用スクリプト作成
- `test_db_integration.py` ファイルを作成し、以下を追加:
```python
from db_manager import init_db, get_db
init_db()
print("Database integration test structure ready")
```

---
*次は P2 ファイル（ステップ 25-48）に続きます*