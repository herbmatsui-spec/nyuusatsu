# -*- coding: utf-8 -*-
import sqlite3
conn = sqlite3.connect('bids_system.db')
cur = conn.cursor()

# bidsテーブルのスキーマ
cur.execute('PRAGMA table_info(bids)')
print('=== bids table schema ===')
for r in cur.fetchall():
    print('  %s: %s' % (r[1], r[2]))

# bid_sourcesテーブルのスキーマ
cur.execute('PRAGMA table_info(bid_sources)')
print()
print('=== bid_sources table schema ===')
for r in cur.fetchall():
    print('  %s: %s' % (r[1], r[2]))

# prefecturesテーブルのスキーマ
cur.execute('PRAGMA table_info(prefectures)')
print()
print('=== prefectures table schema ===')
for r in cur.fetchall():
    print('  %s: %s' % (r[1], r[2]))

# Hokkaidoのbid_sources
cur.execute('SELECT id, source_type, url, is_active FROM bid_sources WHERE prefecture_id = 1')
print()
print('=== Hokkaido bid_sources ===')
for r in cur.fetchall():
    print('  ID=%s, type=%s, url=%s..., active=%s' % (r[0], r[1], r[2][:60], r[3]))

# Hokkaidoのbids
cur.execute('SELECT id, title, organization, category, estimated_amount, announcement_date, deadline, status FROM bids LIMIT 5')
print()
print('=== Sample bids ===')
for r in cur.fetchall():
    print('  ID=%s, title=%s...' % (r[0], (r[1][:40] if r[1] else None)))
    print('    org=%s, cat=%s, amount=%s, announce=%s, deadline=%s, status=%s' % (r[2], r[3], r[4], r[5], r[6], r[7]))

# bidsテーブルの全てのカラムでHokkaidoを検索
print()
print('=== Looking for Hokkaido bids ===')
cur.execute('SELECT COUNT(*) FROM bids')
print('Total bids:', cur.fetchone()[0])

conn.close()