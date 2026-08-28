import sqlite3
import os

def migrate_add_prefecture_code():
    db_path = "bids_system.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # カラムが存在するか確認
        cursor.execute("PRAGMA table_info(bids)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "prefecture_code" in columns:
            print("Column 'prefecture_code' already exists. Skipping.")
        else:
            print("Adding column 'prefecture_code' to 'bids' table...")
            # SQLiteではALTER TABLE ADD COLUMNを使用
            cursor.execute("ALTER TABLE bids ADD COLUMN prefecture_code VARCHAR(20)")
            conn.commit()
            print("Successfully added 'prefecture_code' column.")
        
        conn.close()
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate_add_prefecture_code()
