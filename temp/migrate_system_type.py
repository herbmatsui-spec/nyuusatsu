import sys
sys.path.append('D:/入札システム')
import sqlite3
conn = sqlite3.connect('D:/入札システム/bids_system.db')
cur = conn.cursor()
try:
    cur.execute('ALTER TABLE agencies ADD COLUMN system_type TEXT')
    conn.commit()
    print('Added column system_type')
except Exception as e:
    print('Error:', e)
conn.close()
