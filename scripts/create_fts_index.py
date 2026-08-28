import logging
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_fts_index():
    """
    SQLite FTS5 全文検索インデックスを作成する。
    bids テーブルの project_name, organization, full_text を結合してインデックス化する。
    """
    from sqlalchemy import create_engine, text
    from database.config import DATABASE_URL

    logger.info("Creating FTS5 Full-Text Search index...")
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # 1. FTS5 仮想テーブルの作成
            # content='bids' を指定することで外部コンテンツテーブルとして構築し、ストレージを節約
            conn.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS bid_search_index USING fts5(
                    project_name, 
                    organization, 
                    full_text, 
                    content='bids', 
                    tokenize='unicode61'
                );
            """))
            
            # 2. 既存データのインデックス同期
            # bids テーブルからデータをコピーしてインデックスを構築
            conn.execute(text("""
                INSERT INTO bid_search_index(rowid, project_name, organization, full_text)
                SELECT id, project_name, organization, full_text FROM bids;
            """))
            
            # 3. トリガーの設定 (bids テーブルの更新に合わせて FTS インデックスを自動更新)
            # INSERT トリガー
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS bid_ai AFTER INSERT ON bids BEGIN
                    INSERT INTO bid_search_index(rowid, project_name, organization, full_text)
                    VALUES (new.id, new.project_name, new.organization, new.full_text);
                END;
            """))
            
            # DELETE トリガー
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS bid_ad AFTER DELETE ON bids BEGIN
                    INSERT INTO bid_search_index(bid_search_index, rowid, project_name, organization, full_text)
                    VALUES('delete', old.id, old.project_name, old.organization, old.full_text);
                END;
            """))
            
            # UPDATE トリガー
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS bid_au AFTER UPDATE ON bids BEGIN
                    INSERT INTO bid_search_index(bid_search_index, rowid, project_name, organization, full_text)
                    VALUES('delete', old.id, old.project_name, old.organization, old.full_text);
                    INSERT INTO bid_search_index(rowid, project_name, organization, full_text)
                    VALUES (new.id, new.project_name, new.organization, new.full_text);
                END;
            """))
            
            conn.commit()
            logger.info("FTS5 index and triggers created successfully.")
            return True
    except Exception as e:
        logger.error(f"Failed to create FTS5 index: {e}")
        return False

if __name__ == "__main__":
    if create_fts_index():
        logger.info("FTS5 index is ready.")
    else:
        sys.exit(1)
