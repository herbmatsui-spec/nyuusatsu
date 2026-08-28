import sqlite3
import os

REQUIRED_TABLES = [
    "document_archives",
    "extraction_results",
    "saved_searches",
    "notification_channels",
    "bid_assignments",
    "organizations",
    "users",
    "roles",
    "user_roles",
    "price_predictions",
    "audit_logs",
    "bids",
]

EXPECTED_COLUMNS = {
    "extraction_results": ["question_deadline", "submit_deadline", "opening_date", "bid_id"],
    "bids": ["org_id"],
}

print("=== DB Table Verification ===")
conn = sqlite3.connect('bids_system.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
existing = {r[0] for r in cursor.fetchall()}

missing = []
for t in REQUIRED_TABLES:
    if t in existing:
        print(f"  [OK] {t}")
    else:
        print(f"  [MISSING] {t}")
        missing.append(t)

for tbl, cols in EXPECTED_COLUMNS.items():
    cursor.execute(f"PRAGMA table_info({tbl})")
    actual_cols = {r[1] for r in cursor.fetchall()}
    for col in cols:
        if col in actual_cols:
            print(f"  [OK] {tbl}.{col}")
        else:
            print(f"  [MISSING] {tbl}.{col}")
            missing.append(f"{tbl}.{col}")

cursor.execute("SELECT version_num FROM alembic_version")
print(f"\nAlembic version: {[r[0] for r in cursor.fetchall()]}")
conn.close()

print("\n=== Archive Directory ===")
archive_exists = os.path.isdir("data/archives")
print(f"  data/archives exists: {archive_exists}")

if missing:
    print(f"\n!!! MISSING ITEMS: {missing}")
else:
    print("\n=== ALL DB CHECKS PASSED ===")
