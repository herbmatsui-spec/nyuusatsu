import sqlite3
import os
from datetime import datetime
from db_manager import DB_PATH

def detect_new_bids(new_urls_list):
    """
    Compare new_urls_list with the database to find bids that haven't been notified.
    new_urls_list: list of dicts [{'url': '...', 'title': '...'}]
    Returns: list of new bids and total count.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_bids = []
    
    for bid in new_urls_list:
        url = bid['url']
        title = bid.get('title', 'No Title')
        
        # Check if URL already exists in crawled_urls
        cursor.execute('SELECT id FROM crawled_urls WHERE url = ?', (url,))
        row = cursor.fetchone()
        
        if row is None:
            # It's a new bid
            cursor.execute('''
                INSERT INTO crawled_urls (url, title, found_time, notified)
                VALUES (?, ?, ?, 0)
            ''', (url, title, datetime.now().isoformat()))
            new_bids.append(bid)
        else:
            # Check if it was notified
            cursor.execute('SELECT notified FROM crawled_urls WHERE url = ?', (url,))
            notified = cursor.fetchone()[0]
            if not notified:
                new_bids.append(bid)
    
    conn.commit()
    conn.close()
    
    return new_bids

def mark_as_notified(urls):
    """Mark specific URLs as notified in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for url in urls:
        cursor.execute('UPDATE crawled_urls SET notified = 1 WHERE url = ?', (url,))
    conn.commit()
    conn.close()
