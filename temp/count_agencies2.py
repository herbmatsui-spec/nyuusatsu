import sqlite3, json
conn = sqlite3.connect('bids_system.db')
cur = conn.cursor()
cur.execute('PRAGMA table_info(agencies)')
schema = cur.fetchall()
cur.execute('SELECT COUNT(*) FROM agencies')
count = cur.fetchone()[0]
print('SCHEMA:', json.dumps(schema))
print('COUNT:', count)
