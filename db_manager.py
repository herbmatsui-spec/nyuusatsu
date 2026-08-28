import sqlite3
import os
import logging
from datetime import datetime

# DB path
DB_PATH = os.path.join("data", "crawl_history.db")

def init_db():
    """Initialize the database and create required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Crawl history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawl_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawl_time DATETIME NOT NULL,
            url_count INTEGER NOT NULL,
            new_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT
        )
    ''')
    
    # Crawled URLs table for diff detection
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawled_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            found_time DATETIME NOT NULL,
            notified BOOLEAN DEFAULT 0
        )
    ''')
    
    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully.")

def record_crawl_history(url_count, new_count, status, error_message=None):
    """Record the result of a crawl session."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO crawl_history (crawl_time, url_count, new_count, status, error_message)
        VALUES (?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), url_count, new_count, status, error_message))
    conn.commit()
    conn.close()

def get_crawl_history(limit=50):
    """Retrieve recent crawl history."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM crawl_history ORDER BY crawl_time DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
